from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy.orm import Session

from app.models.client_account import ClientAccount
from app.models.llm_generation_event import LLMGenerationEvent
from app.services.generation_guardrails import evaluate_generation_guardrails
from app.services.tariff_policy import DEFAULT_PLAN_POLICIES, resolve_plan_access_flag, resolve_plan_policy

DEFAULT_TARGET_MARGIN_PCT = Decimal("70")
DEFAULT_CONTINGENCY_PCT = Decimal("15")
DEFAULT_PLATFORM_OVERHEAD_USD = Decimal("9.00")
DEFAULT_CHANNEL_OVERHEAD_USD = Decimal("2.00")
DEFAULT_SUCCESS_RATIO = Decimal("0.85")
USD_6 = Decimal("0.000001")
USD_2 = Decimal("0.01")

DEFAULT_OPERATION_BASELINES: dict[str, dict[str, Any]] = {
    "ideas": {"label": "Идеи", "fallback_cost_usd": Decimal("0.002500"), "included_share": 0.25, "success_ratio": Decimal("0.95")},
    "content_plan": {"label": "Контент-план", "fallback_cost_usd": Decimal("0.004500"), "included_share": 0.10, "success_ratio": Decimal("0.90")},
    "draft": {"label": "Черновик", "fallback_cost_usd": Decimal("0.006500"), "included_share": 0.40, "success_ratio": Decimal("0.85")},
    "regenerate_draft": {"label": "Регенерация", "fallback_cost_usd": Decimal("0.007000"), "included_share": 0.15, "success_ratio": Decimal("0.80")},
    "rewrite_draft": {"label": "Рерайт", "fallback_cost_usd": Decimal("0.003000"), "included_share": 0.10, "success_ratio": Decimal("0.90")},
}

DEFAULT_PLAN_CATALOG: list[dict[str, Any]] = [
    {
        "plan_code": policy.plan_code,
        "label": policy.label,
        "service_tier": policy.service_tier,
        "execution_mode": policy.execution_mode,
        "monthly_fee_usd": Decimal("0.00") if policy.plan_code == "trial" else None,
        "included_channels": policy.included_channels,
        "included_generations": policy.included_generations,
        "max_tasks_per_day": policy.max_tasks_per_day,
        "allowed_preset_codes": list(policy.allowed_preset_codes),
        "default_preset_code": policy.default_preset_code,
        "access_flag": policy.access_flag,
        "allowed_generation_operations": list(policy.allowed_generation_operations),
    }
    for policy in DEFAULT_PLAN_POLICIES.values()
]


@dataclass(slots=True)
class PricingOperationSummary:
    operation_type: str
    label: str
    successful_events_count: int
    total_events_count: int
    average_cost_usd: Decimal
    target_margin_pct: Decimal
    contingency_pct: Decimal
    recommended_unit_price_usd: Decimal
    recommended_unit_margin_usd: Decimal
    recommended_unit_margin_pct: Decimal | None
    delta_vs_average_cost_usd: Decimal
    observed_share_pct: Decimal
    included_share: Decimal


@dataclass(slots=True)
class PricingPlanSummary:
    plan_code: str
    label: str
    service_tier: str
    execution_mode: str
    monthly_fee_usd: Decimal
    included_channels: int
    included_generations: int
    max_tasks_per_day: int
    allowed_preset_codes: list[str]
    default_preset_code: str
    access_flag: str
    allowed_generation_operations: list[str]
    blended_generation_cost_usd: Decimal
    observed_blended_generation_cost_usd: Decimal
    included_cogs_usd: Decimal
    projected_sample_generation_cost_usd: Decimal
    projected_sample_total_cogs_usd: Decimal
    target_margin_pct: Decimal
    projected_gross_margin_usd: Decimal
    projected_gross_margin_pct: Decimal | None
    projected_sample_gross_margin_usd: Decimal
    projected_sample_gross_margin_pct: Decimal | None
    overage_unit_price_usd: Decimal


@dataclass(slots=True)
class ClientPricingSummary:
    client_id: Any
    generated_at: datetime
    target_margin_pct: Decimal
    contingency_pct: Decimal
    platform_overhead_usd: Decimal
    channel_overhead_usd: Decimal
    active_plan_code: str
    currency: str
    operation_rates: list[PricingOperationSummary]
    plan_catalog: list[PricingPlanSummary]
    assumptions: dict[str, Any]


def build_client_pricing_summary(db: Session, client_account: ClientAccount) -> ClientPricingSummary:
    settings = client_account.settings or {}
    pricing_settings = settings.get("pricing_model", {}) if isinstance(settings, dict) else {}
    target_margin_pct = _to_decimal(pricing_settings.get("target_margin_pct"), DEFAULT_TARGET_MARGIN_PCT)
    contingency_pct = _to_decimal(pricing_settings.get("contingency_pct"), DEFAULT_CONTINGENCY_PCT)
    platform_overhead_usd = _to_decimal(pricing_settings.get("platform_overhead_usd"), DEFAULT_PLATFORM_OVERHEAD_USD)
    channel_overhead_usd = _to_decimal(pricing_settings.get("channel_overhead_usd"), DEFAULT_CHANNEL_OVERHEAD_USD)
    currency = str(pricing_settings.get("currency") or "USD").upper()

    events = [
        event
        for event in db.query(LLMGenerationEvent).all()
        if event.client_id == client_account.id or event.client_id == client_account.owner_user_id
    ]
    successful_events = [event for event in events if (event.status or "").lower() == "succeeded"]

    operation_rates = _build_operation_rates(
        successful_events=successful_events,
        total_events=events,
        target_margin_pct=target_margin_pct,
        contingency_pct=contingency_pct,
        overrides=pricing_settings.get("operation_overrides") if isinstance(pricing_settings, dict) else None,
    )

    guardrails = evaluate_generation_guardrails(db, project=None, operation_type=None)
    # evaluate_generation_guardrails(project=None) yields empty snapshots today, so derive included quotas from explicit settings.
    del guardrails

    plan_catalog = _build_plan_catalog(
        operation_rates,
        pricing_settings=pricing_settings,
        target_margin_pct=target_margin_pct,
        platform_overhead_usd=platform_overhead_usd,
        channel_overhead_usd=channel_overhead_usd,
    )
    return ClientPricingSummary(
        client_id=client_account.id,
        generated_at=datetime.now(UTC),
        target_margin_pct=target_margin_pct.quantize(USD_2),
        contingency_pct=contingency_pct.quantize(USD_2),
        platform_overhead_usd=_q2(platform_overhead_usd),
        channel_overhead_usd=_q2(channel_overhead_usd),
        active_plan_code=resolve_plan_policy(client_account).plan_code,
        currency=currency,
        operation_rates=operation_rates,
        plan_catalog=plan_catalog,
        assumptions={
            "billing_cycle": getattr(client_account.billing_cycle, "value", client_account.billing_cycle) or "monthly",
            "success_events_sample_size": len(successful_events),
            "all_events_sample_size": len(events),
            "blended_generation_cost_usd": str(_blended_generation_cost(operation_rates)),
            "observed_blended_generation_cost_usd": str(_observed_blended_generation_cost(operation_rates)),
        },
    )


def _build_operation_rates(*, successful_events: list[LLMGenerationEvent], total_events: list[LLMGenerationEvent], target_margin_pct: Decimal, contingency_pct: Decimal, overrides: dict[str, Any] | None) -> list[PricingOperationSummary]:
    rows: list[PricingOperationSummary] = []
    overrides = overrides or {}
    successful_events_total = len(successful_events)
    for operation_type, baseline in DEFAULT_OPERATION_BASELINES.items():
        success_bucket = [event for event in successful_events if event.operation_type == operation_type]
        total_bucket = [event for event in total_events if event.operation_type == operation_type]
        average_cost = _average_cost(success_bucket, baseline["fallback_cost_usd"])
        if operation_type in overrides and isinstance(overrides[operation_type], dict):
            override = overrides[operation_type]
            average_cost = _to_decimal(override.get("cost_floor_usd"), average_cost)
        recommended = _recommended_price(
            average_cost_usd=average_cost,
            target_margin_pct=target_margin_pct,
            contingency_pct=contingency_pct,
            success_ratio=_to_decimal(baseline.get("success_ratio"), DEFAULT_SUCCESS_RATIO),
        )
        margin_usd = recommended - average_cost
        margin_pct = None
        if recommended > 0:
            margin_pct = ((margin_usd / recommended) * Decimal("100")).quantize(USD_2, rounding=ROUND_HALF_UP)
        observed_share_pct = Decimal("0")
        if successful_events_total > 0:
            observed_share_pct = (Decimal(len(success_bucket)) / Decimal(successful_events_total) * Decimal("100")).quantize(USD_2, rounding=ROUND_HALF_UP)
        rows.append(
            PricingOperationSummary(
                operation_type=operation_type,
                label=str(baseline["label"]),
                successful_events_count=len(success_bucket),
                total_events_count=len(total_bucket),
                average_cost_usd=_q6(average_cost),
                target_margin_pct=target_margin_pct.quantize(USD_2),
                contingency_pct=contingency_pct.quantize(USD_2),
                recommended_unit_price_usd=_q6(recommended),
                recommended_unit_margin_usd=_q6(margin_usd),
                recommended_unit_margin_pct=margin_pct,
                delta_vs_average_cost_usd=_q6(recommended - average_cost),
                observed_share_pct=observed_share_pct,
                included_share=Decimal(str(baseline["included_share"])).quantize(USD_2),
            )
        )
    return rows


def _build_plan_catalog(operation_rates: list[PricingOperationSummary], *, pricing_settings: dict[str, Any], target_margin_pct: Decimal, platform_overhead_usd: Decimal, channel_overhead_usd: Decimal) -> list[PricingPlanSummary]:
    catalog = pricing_settings.get("plan_catalog") if isinstance(pricing_settings.get("plan_catalog"), list) else DEFAULT_PLAN_CATALOG
    blended_generation_cost = _blended_generation_cost(operation_rates)
    observed_blended_generation_cost = _observed_blended_generation_cost(operation_rates)
    overage_unit_price = _q6(max((row.recommended_unit_price_usd for row in operation_rates), default=Decimal("0")))

    plans: list[PricingPlanSummary] = []
    for raw_plan in catalog:
        included_channels = int(raw_plan.get("included_channels") or 1)
        included_generations = int(raw_plan.get("included_generations") or 0)
        included_cogs = _q2(platform_overhead_usd + (channel_overhead_usd * included_channels) + (blended_generation_cost * included_generations))
        sample_generation_cost = _q2(observed_blended_generation_cost * included_generations)
        sample_total_cogs = _q2(platform_overhead_usd + (channel_overhead_usd * included_channels) + sample_generation_cost)
        monthly_fee_raw = raw_plan.get("monthly_fee_usd")
        if monthly_fee_raw is None:
            monthly_fee = _price_for_target_margin(included_cogs, target_margin_pct)
        else:
            monthly_fee = _q2(_to_decimal(monthly_fee_raw, Decimal("0")))
        gross_margin = _q2(monthly_fee - included_cogs)
        gross_margin_pct = None
        if monthly_fee > 0:
            gross_margin_pct = ((gross_margin / monthly_fee) * Decimal("100")).quantize(USD_2, rounding=ROUND_HALF_UP)
        sample_gross_margin = _q2(monthly_fee - sample_total_cogs)
        sample_gross_margin_pct = None
        if monthly_fee > 0:
            sample_gross_margin_pct = ((sample_gross_margin / monthly_fee) * Decimal("100")).quantize(USD_2, rounding=ROUND_HALF_UP)
        plans.append(
            PricingPlanSummary(
                plan_code=str(raw_plan.get("plan_code") or "custom"),
                label=str(raw_plan.get("label") or raw_plan.get("plan_code") or "Custom"),
                service_tier=str(raw_plan.get("service_tier") or "custom"),
                execution_mode=str(raw_plan.get("execution_mode") or "custom"),
                monthly_fee_usd=monthly_fee,
                included_channels=included_channels,
                included_generations=included_generations,
                max_tasks_per_day=int(raw_plan.get("max_tasks_per_day") or 0),
                allowed_preset_codes=[str(item) for item in (raw_plan.get("allowed_preset_codes") or [])],
                default_preset_code=str(raw_plan.get("default_preset_code") or "starter_3"),
                access_flag=str(raw_plan.get("access_flag") or 'paid'),
                allowed_generation_operations=[str(item) for item in (raw_plan.get("allowed_generation_operations") or [])],
                blended_generation_cost_usd=_q6(blended_generation_cost),
                observed_blended_generation_cost_usd=_q6(observed_blended_generation_cost),
                included_cogs_usd=included_cogs,
                projected_sample_generation_cost_usd=sample_generation_cost,
                projected_sample_total_cogs_usd=sample_total_cogs,
                target_margin_pct=target_margin_pct.quantize(USD_2),
                projected_gross_margin_usd=gross_margin,
                projected_gross_margin_pct=gross_margin_pct,
                projected_sample_gross_margin_usd=sample_gross_margin,
                projected_sample_gross_margin_pct=sample_gross_margin_pct,
                overage_unit_price_usd=overage_unit_price,
            )
        )
    return plans


def _average_cost(events: list[LLMGenerationEvent], fallback: Decimal) -> Decimal:
    if not events:
        return fallback
    total = sum((Decimal(str(event.estimated_cost_usd or 0)) for event in events), Decimal("0"))
    if total <= 0:
        return fallback
    return total / Decimal(len(events))


def _blended_generation_cost(operation_rates: list[PricingOperationSummary]) -> Decimal:
    if not operation_rates:
        return Decimal("0")
    total = Decimal("0")
    for row in operation_rates:
        total += row.average_cost_usd * row.included_share
    return _q6(total)


def _observed_blended_generation_cost(operation_rates: list[PricingOperationSummary]) -> Decimal:
    if not operation_rates:
        return Decimal("0")
    observed_total = sum((row.observed_share_pct for row in operation_rates), Decimal("0"))
    if observed_total <= 0:
        return _blended_generation_cost(operation_rates)
    total = Decimal("0")
    for row in operation_rates:
        total += row.average_cost_usd * (row.observed_share_pct / Decimal("100"))
    return _q6(total)


def _recommended_price(*, average_cost_usd: Decimal, target_margin_pct: Decimal, contingency_pct: Decimal, success_ratio: Decimal) -> Decimal:
    adjusted_cost = average_cost_usd * (Decimal("1") + (contingency_pct / Decimal("100")))
    if success_ratio > 0:
        adjusted_cost = adjusted_cost / success_ratio
    return _price_for_target_margin(adjusted_cost, target_margin_pct)


def _price_for_target_margin(cost: Decimal, target_margin_pct: Decimal) -> Decimal:
    margin_ratio = target_margin_pct / Decimal("100")
    denominator = Decimal("1") - margin_ratio
    if denominator <= 0:
        denominator = Decimal("0.01")
    return _q2(cost / denominator)


def _to_decimal(value: Any, fallback: Decimal) -> Decimal:
    if value is None or value == "":
        return fallback
    return Decimal(str(value))


def _q2(value: Decimal) -> Decimal:
    return value.quantize(USD_2, rounding=ROUND_HALF_UP)


def _q6(value: Decimal) -> Decimal:
    return value.quantize(USD_6, rounding=ROUND_HALF_UP)
