from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from app.core.config import settings
from app.services.generation_observability import emit_generation_event, emit_generation_warning, record_provider_health


class LLMProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        provider: str,
        status_code: int | None = None,
        raw_error: Any = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.raw_error = raw_error
        self.retryable = retryable


class LLMCircuitBreakerOpenError(LLMProviderError):
    pass


@dataclass(slots=True)
class LLMGenerationRequest:
    system_prompt: str
    user_prompt: str
    model: str | None = None
    max_tokens: int = 900
    temperature: float = 0.7


@dataclass(slots=True)
class LLMGenerationResult:
    provider: str
    model: str
    output_text: str
    finish_reason: str | None
    request_id: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: int
    raw_error: Any = None
    failover: dict[str, Any] | None = None


@dataclass(slots=True)
class LLMCircuitBreakerState:
    consecutive_failures: int = 0
    opened_until: float = 0.0


_CIRCUIT_BREAKERS: dict[str, LLMCircuitBreakerState] = {}
_RETRYABLE_HTTP_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


class BaseLLMAdapter:
    provider_name = "base"

    def generate(self, payload: LLMGenerationRequest) -> LLMGenerationResult:
        raise NotImplementedError


class StubLLMAdapter(BaseLLMAdapter):
    provider_name = "stub"

    def generate(self, payload: LLMGenerationRequest) -> LLMGenerationResult:
        started = time.perf_counter()
        output = self._build_stub_output(payload)
        latency_ms = max(int((time.perf_counter() - started) * 1000), 1)
        return LLMGenerationResult(
            provider=self.provider_name,
            model=payload.model or settings.llm_model_default,
            output_text=output,
            finish_reason="stop",
            request_id="stub-request",
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            latency_ms=latency_ms,
            raw_error=None,
        )

    def _build_stub_output(self, payload: LLMGenerationRequest) -> str:
        system_prompt = payload.system_prompt.lower()
        if "content ideas" in system_prompt:
            return self._build_stub_ideas(payload.user_prompt)
        if "content plan" in system_prompt:
            return self._build_stub_content_plan()
        return (
            "# Generated draft\n\n"
            f"{payload.user_prompt.strip()}\n\n"
            "---\n"
            "Generated in stub mode. Replace LLM_PROVIDER to call a real model."
        )

    def _build_stub_ideas(self, user_prompt: str) -> str:
        count = 10
        for line in user_prompt.splitlines():
            if "Need " in line and " distinct ideas" in line:
                chunk = line.split("Need ", 1)[1].split(" distinct ideas", 1)[0].strip()
                if chunk.isdigit():
                    count = max(int(chunk), 1)
                break

        brief = ""
        for line in user_prompt.splitlines():
            if line.startswith("Brief:"):
                brief = line.split("Brief:", 1)[1].strip()
                break
        brief = brief or "полезные посты для Telegram-канала"
        base = brief.rstrip('. ')
        return "\n".join(
            f"{index + 1}. {base}: идея {index + 1}"
            for index in range(count)
        )

    def _build_stub_content_plan(self) -> str:
        return (
            "Понедельник — экспертный разбор\n"
            "Среда — практический чеклист\n"
            "Пятница — кейс с выводами"
        )


class JSONHTTPAdapter(BaseLLMAdapter):
    endpoint_path = ""

    def __init__(self, *, base_url: str | None = None, api_key: str | None = None):
        resolved_base_url = base_url or settings.llm_base_url or self.default_base_url()
        self.base_url = resolved_base_url.rstrip("/")
        self.api_key = api_key or settings.llm_api_key

    def default_base_url(self) -> str:
        raise NotImplementedError

    def build_url(self) -> str:
        return f"{self.base_url}{self.endpoint_path}"

    def build_headers(self) -> dict[str, str]:
        raise NotImplementedError

    def build_body(self, payload: LLMGenerationRequest) -> dict[str, Any]:
        raise NotImplementedError

    def parse_response(self, response_json: dict[str, Any], headers: Any, latency_ms: int) -> LLMGenerationResult:
        raise NotImplementedError

    def generate(self, payload: LLMGenerationRequest) -> LLMGenerationResult:
        self._raise_if_circuit_open()
        body = json.dumps(self.build_body(payload)).encode("utf-8")
        req = request.Request(
            self.build_url(),
            data=body,
            headers=self.build_headers() | {"Content-Type": "application/json"},
            method="POST",
        )
        attempts = max(settings.llm_max_retries, 0) + 1
        last_error: LLMProviderError | None = None
        for attempt_index in range(1, attempts + 1):
            started = time.perf_counter()
            try:
                with request.urlopen(req, timeout=settings.llm_timeout_seconds) as response:
                    raw = response.read().decode("utf-8")
                    response_json = json.loads(raw)
                    latency_ms = max(int((time.perf_counter() - started) * 1000), 1)
                    result = self.parse_response(response_json, response.headers, latency_ms)
                    self._record_circuit_success()
                    health = record_provider_health(
                        self.provider_name,
                        model=result.model,
                        ok=True,
                        latency_ms=result.latency_ms,
                        request_id=result.request_id,
                        failover=result.failover,
                    )
                    emit_generation_event(
                        'llm provider request succeeded',
                        provider=self.provider_name,
                        model=result.model,
                        latency_ms=result.latency_ms,
                        request_id=result.request_id,
                        finish_reason=result.finish_reason,
                        prompt_tokens=result.prompt_tokens,
                        completion_tokens=result.completion_tokens,
                        total_tokens=result.total_tokens,
                        provider_health=health,
                    )
                    return result
            except error.HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="ignore")
                provider_error = LLMProviderError(
                    f"{self.provider_name} request failed with status {exc.code}",
                    provider=self.provider_name,
                    status_code=exc.code,
                    raw_error=raw,
                    retryable=exc.code in _RETRYABLE_HTTP_STATUS_CODES,
                )
            except error.URLError as exc:
                provider_error = LLMProviderError(
                    f"{self.provider_name} request failed: {exc.reason}",
                    provider=self.provider_name,
                    raw_error=str(exc.reason),
                    retryable=True,
                )
            last_error = provider_error
            self._record_circuit_failure(provider_error)
            health = record_provider_health(
                self.provider_name,
                model=payload.model or settings.llm_model_default,
                ok=False,
                retryable=provider_error.retryable,
                status_code=provider_error.status_code,
                error_message=str(provider_error),
            )
            emit_generation_warning(
                'llm provider request failed',
                provider=self.provider_name,
                model=payload.model or settings.llm_model_default,
                attempt=attempt_index,
                attempts=attempts,
                retryable=provider_error.retryable,
                status_code=provider_error.status_code,
                error=str(provider_error),
                provider_health=health,
            )
            if attempt_index >= attempts or not provider_error.retryable:
                raise provider_error
            retry_delay = self._retry_delay_seconds(attempt_index)
            emit_generation_warning(
                'llm provider retry scheduled',
                provider=self.provider_name,
                model=payload.model or settings.llm_model_default,
                attempt=attempt_index,
                retry_delay_seconds=retry_delay,
            )
            time.sleep(retry_delay)
        assert last_error is not None
        raise last_error

    def _retry_delay_seconds(self, attempt_index: int) -> float:
        base_delay = max(settings.llm_retry_base_delay_ms, 1) / 1000
        max_delay = max(settings.llm_retry_max_delay_ms, settings.llm_retry_base_delay_ms) / 1000
        exp_delay = min(max_delay, base_delay * (2 ** max(attempt_index - 1, 0)))
        jitter_window = min(exp_delay * 0.2, 1.0)
        return max(0.0, exp_delay + random.uniform(0.0, jitter_window))

    def _circuit_state(self) -> LLMCircuitBreakerState:
        return _CIRCUIT_BREAKERS.setdefault(self.provider_name, LLMCircuitBreakerState())

    def _raise_if_circuit_open(self) -> None:
        state = self._circuit_state()
        now = time.time()
        if state.opened_until > now:
            retry_after = max(int(state.opened_until - now), 1)
            raise LLMCircuitBreakerOpenError(
                f"{self.provider_name} circuit breaker is open for {retry_after}s due to recent provider failures",
                provider=self.provider_name,
                retryable=True,
            )
        if state.opened_until and state.opened_until <= now:
            state.opened_until = 0.0
            state.consecutive_failures = 0

    def _record_circuit_success(self) -> None:
        state = self._circuit_state()
        state.consecutive_failures = 0
        state.opened_until = 0.0

    def _record_circuit_failure(self, provider_error: LLMProviderError) -> None:
        state = self._circuit_state()
        if provider_error.retryable:
            state.consecutive_failures += 1
        else:
            state.consecutive_failures = 0
            state.opened_until = 0.0
            return
        if state.consecutive_failures >= settings.llm_circuit_breaker_threshold:
            state.opened_until = time.time() + settings.llm_circuit_breaker_cooldown_seconds


class OpenAICompatibleAdapter(JSONHTTPAdapter):
    endpoint_path = "/chat/completions"

    def default_base_url(self) -> str:
        if settings.llm_provider == "openrouter":
            return "https://openrouter.ai/api/v1"
        return "https://api.openai.com/v1"

    def build_headers(self) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if self.provider_name == "openrouter":
            headers["HTTP-Referer"] = "https://telegram-channel-factory.local"
            headers["X-Title"] = settings.app_name
        return headers

    def build_body(self, payload: LLMGenerationRequest) -> dict[str, Any]:
        return {
            "model": payload.model or settings.llm_model_default,
            "messages": [
                {"role": "system", "content": payload.system_prompt},
                {"role": "user", "content": payload.user_prompt},
            ],
            "temperature": payload.temperature,
            "max_tokens": payload.max_tokens,
        }

    def parse_response(self, response_json: dict[str, Any], headers: Any, latency_ms: int) -> LLMGenerationResult:
        choice = (response_json.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        usage = response_json.get("usage") or {}
        return LLMGenerationResult(
            provider=self.provider_name,
            model=response_json.get("model") or settings.llm_model_default,
            output_text=(message.get("content") or "").strip(),
            finish_reason=choice.get("finish_reason"),
            request_id=headers.get("x-request-id") or response_json.get("id"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            latency_ms=latency_ms,
            raw_error=None,
        )


class OpenAIAdapter(OpenAICompatibleAdapter):
    provider_name = "openai"


class OpenRouterAdapter(OpenAICompatibleAdapter):
    provider_name = "openrouter"


class AnthropicAdapter(JSONHTTPAdapter):
    provider_name = "anthropic"
    endpoint_path = "/v1/messages"

    def default_base_url(self) -> str:
        return "https://api.anthropic.com"

    def build_headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
        }

    def build_body(self, payload: LLMGenerationRequest) -> dict[str, Any]:
        return {
            "model": payload.model or settings.llm_model_default,
            "system": payload.system_prompt,
            "messages": [{"role": "user", "content": payload.user_prompt}],
            "temperature": payload.temperature,
            "max_tokens": payload.max_tokens,
        }

    def parse_response(self, response_json: dict[str, Any], headers: Any, latency_ms: int) -> LLMGenerationResult:
        content = response_json.get("content") or []
        text_blocks = [block.get("text", "") for block in content if block.get("type") == "text"]
        usage = response_json.get("usage") or {}
        prompt_tokens = usage.get("input_tokens")
        completion_tokens = usage.get("output_tokens")
        total_tokens = None
        if prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens
        return LLMGenerationResult(
            provider=self.provider_name,
            model=response_json.get("model") or settings.llm_model_default,
            output_text="\n".join(part.strip() for part in text_blocks if part.strip()),
            finish_reason=response_json.get("stop_reason"),
            request_id=headers.get("request-id") or response_json.get("id"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            raw_error=None,
        )


class GeminiAdapter(JSONHTTPAdapter):
    provider_name = "gemini"
    endpoint_path = ""

    def default_base_url(self) -> str:
        return "https://generativelanguage.googleapis.com/v1beta"

    def build_url(self) -> str:
        model = settings.llm_model_default
        return f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"

    def build_headers(self) -> dict[str, str]:
        return {}

    def build_body(self, payload: LLMGenerationRequest) -> dict[str, Any]:
        model = payload.model or settings.llm_model_default
        return {
            "systemInstruction": {
                "parts": [{"text": payload.system_prompt}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": payload.user_prompt}],
                }
            ],
            "generationConfig": {
                "temperature": payload.temperature,
                "maxOutputTokens": payload.max_tokens,
            },
            "model": model,
        }

    def parse_response(self, response_json: dict[str, Any], headers: Any, latency_ms: int) -> LLMGenerationResult:
        candidates = response_json.get("candidates") or [{}]
        candidate = candidates[0]
        content = candidate.get("content") or {}
        parts = content.get("parts") or []
        usage = response_json.get("usageMetadata") or {}
        return LLMGenerationResult(
            provider=self.provider_name,
            model=settings.llm_model_default,
            output_text="\n".join(part.get("text", "").strip() for part in parts if part.get("text")),
            finish_reason=candidate.get("finishReason"),
            request_id=headers.get("x-request-id") or response_json.get("responseId"),
            prompt_tokens=usage.get("promptTokenCount"),
            completion_tokens=usage.get("candidatesTokenCount"),
            total_tokens=usage.get("totalTokenCount"),
            latency_ms=latency_ms,
            raw_error=None,
        )


def reset_llm_circuit_breakers() -> None:
    _CIRCUIT_BREAKERS.clear()


def get_llm_adapter(provider: str | None = None) -> BaseLLMAdapter:
    provider_name = (provider or settings.llm_provider).lower()
    adapters: dict[str, type[BaseLLMAdapter]] = {
        "stub": StubLLMAdapter,
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "openrouter": OpenRouterAdapter,
        "gemini": GeminiAdapter,
    }
    adapter_class = adapters.get(provider_name)
    if adapter_class is None:
        raise ValueError(f"Unsupported LLM provider: {provider_name}")
    return adapter_class()


def generate_with_failover(payload: LLMGenerationRequest) -> LLMGenerationResult:
    primary_provider = settings.llm_provider
    primary_model = payload.model or settings.llm_model_default
    primary_adapter = get_llm_adapter(primary_provider)
    emit_generation_event(
        'llm generation requested',
        provider=primary_provider,
        model=primary_model,
        failover_strategy=settings.llm_failover_strategy,
        max_tokens=payload.max_tokens,
        temperature=payload.temperature,
    )
    try:
        return primary_adapter.generate(payload)
    except LLMProviderError as primary_error:
        failover_payload = {
            "strategy": settings.llm_failover_strategy,
            "primary_provider": primary_provider,
            "primary_model": primary_model,
            "primary_error": {
                "message": str(primary_error),
                "status_code": primary_error.status_code,
                "retryable": primary_error.retryable,
                "raw_error": primary_error.raw_error,
            },
        }

        if settings.llm_failover_strategy == "fallback-provider" and settings.llm_fallback_provider:
            fallback_provider = settings.llm_fallback_provider
            fallback_model = settings.llm_fallback_model or primary_model
            fallback_request = LLMGenerationRequest(
                system_prompt=payload.system_prompt,
                user_prompt=payload.user_prompt,
                model=fallback_model,
                max_tokens=payload.max_tokens,
                temperature=payload.temperature,
            )
            try:
                fallback_result = get_llm_adapter(fallback_provider).generate(fallback_request)
                failover_payload.update({
                    "activated": True,
                    "fallback_provider": fallback_provider,
                    "fallback_model": fallback_model,
                    "outcome": "fallback-provider-succeeded",
                })
                fallback_result.failover = failover_payload
                health = record_provider_health(
                    fallback_provider,
                    model=fallback_result.model,
                    ok=True,
                    latency_ms=fallback_result.latency_ms,
                    request_id=fallback_result.request_id,
                    failover=failover_payload,
                )
                emit_generation_event(
                    'llm failover activated',
                    primary_provider=primary_provider,
                    primary_model=primary_model,
                    fallback_provider=fallback_provider,
                    fallback_model=fallback_model,
                    outcome='fallback-provider-succeeded',
                    provider_health=health,
                )
                return fallback_result
            except LLMProviderError as fallback_error:
                failover_payload.update({
                    "activated": True,
                    "fallback_provider": fallback_provider,
                    "fallback_model": fallback_model,
                    "outcome": "fallback-provider-failed",
                    "fallback_error": {
                        "message": str(fallback_error),
                        "status_code": fallback_error.status_code,
                        "retryable": fallback_error.retryable,
                        "raw_error": fallback_error.raw_error,
                    },
                })
                health = record_provider_health(
                    fallback_provider,
                    model=fallback_model,
                    ok=False,
                    retryable=fallback_error.retryable,
                    status_code=fallback_error.status_code,
                    error_message=str(fallback_error),
                    failover=failover_payload,
                )
                emit_generation_warning(
                    'llm failover fallback failed',
                    primary_provider=primary_provider,
                    fallback_provider=fallback_provider,
                    fallback_model=fallback_model,
                    error=str(fallback_error),
                    provider_health=health,
                )

        failover_payload.update({
            "activated": settings.llm_failover_strategy != "disabled",
            "outcome": "graceful-degradation",
        })
        health = record_provider_health(
            primary_provider,
            model=primary_model,
            ok=False,
            retryable=primary_error.retryable,
            status_code=primary_error.status_code,
            error_message=str(primary_error),
            failover=failover_payload,
        )
        emit_generation_warning(
            'llm graceful degradation returned',
            provider=primary_provider,
            model=primary_model,
            error=str(primary_error),
            failover=failover_payload,
            provider_health=health,
        )
        return LLMGenerationResult(
            provider=primary_provider,
            model=primary_model,
            output_text="",
            finish_reason="provider_unavailable",
            request_id=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            latency_ms=0,
            raw_error=primary_error.raw_error,
            failover=failover_payload,
        )
