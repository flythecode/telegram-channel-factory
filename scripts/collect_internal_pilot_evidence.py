from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class PilotEvidenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class EndpointSpec:
    name: str
    path: str
    token_env: str
    filename: str
    query: dict[str, str] | None = None


REQUIRED_ENV = (
    'API_BASE',
    'ADMIN_TOKEN',
    'CLIENT_TOKEN',
    'CHANNEL_ID',
)


def _require_env(name: str) -> str:
    value = os.getenv(name, '').strip()
    if not value:
        raise PilotEvidenceError(f'Missing required environment variable: {name}')
    return value


def _load_runtime() -> tuple[str, str, str, str, Path]:
    api_base = _require_env('API_BASE').rstrip('/')
    admin_token = _require_env('ADMIN_TOKEN')
    client_token = _require_env('CLIENT_TOKEN')
    channel_id = _require_env('CHANNEL_ID')
    today = os.getenv('PILOT_DATE', datetime.now(timezone.utc).strftime('%Y-%m-%d')).strip()
    if not today:
        raise PilotEvidenceError('PILOT_DATE cannot be empty when provided')

    output_dir = Path(os.getenv('OUTPUT_DIR', f'internal-pilot/{today}/raw')).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    return api_base, admin_token, client_token, channel_id, output_dir


def _build_endpoints(channel_id: str) -> Iterable[EndpointSpec]:
    channel_query = {'channel_id': channel_id}
    return (
        EndpointSpec(
            name='client-cost-dashboard',
            path='/api/v1/users/me/client-account/cost-dashboard',
            token_env='CLIENT_TOKEN',
            filename='client-cost-dashboard.json',
        ),
        EndpointSpec(
            name='client-pricing',
            path='/api/v1/users/me/client-account/pricing',
            token_env='CLIENT_TOKEN',
            filename='client-pricing.json',
        ),
        EndpointSpec(
            name='client-cost-dashboard-export',
            path='/api/v1/users/me/client-account/cost-dashboard/export',
            token_env='CLIENT_TOKEN',
            filename='client-cost-dashboard-report.csv',
        ),
        EndpointSpec(
            name='admin-generation-history',
            path='/api/v1/admin/generation/history',
            token_env='ADMIN_TOKEN',
            filename='admin-generation-history.json',
            query={**channel_query, 'limit': '200'},
        ),
        EndpointSpec(
            name='admin-generation-usage',
            path='/api/v1/admin/generation/usage',
            token_env='ADMIN_TOKEN',
            filename='admin-generation-usage.json',
            query=channel_query,
        ),
        EndpointSpec(
            name='admin-generation-cost-breakdown',
            path='/api/v1/admin/generation/cost-breakdown',
            token_env='ADMIN_TOKEN',
            filename='admin-generation-cost-breakdown.json',
            query=channel_query,
        ),
        EndpointSpec(
            name='admin-generation-usage-export',
            path='/api/v1/admin/generation/usage/export',
            token_env='ADMIN_TOKEN',
            filename='admin-generation-usage.csv',
            query=channel_query,
        ),
        EndpointSpec(
            name='admin-generation-cost-breakdown-export',
            path='/api/v1/admin/generation/cost-breakdown/export',
            token_env='ADMIN_TOKEN',
            filename='admin-generation-cost-breakdown.csv',
            query=channel_query,
        ),
    )


def _request_bytes(api_base: str, endpoint: EndpointSpec) -> bytes:
    token = _require_env(endpoint.token_env)
    url = f"{api_base}{endpoint.path}"
    if endpoint.query:
        url = f'{url}?{urlencode(endpoint.query)}'
    request = Request(
        url,
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json, text/csv;q=0.9, */*;q=0.1',
            'User-Agent': 'tcf-internal-pilot-evidence/1.0',
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            return response.read()
    except HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise PilotEvidenceError(f'{endpoint.name} failed with HTTP {exc.code}: {detail}') from exc
    except URLError as exc:
        raise PilotEvidenceError(f'{endpoint.name} failed: {exc.reason}') from exc


def _write_file(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)


def _append_manifest_row(rows: list[dict[str, str]], *, endpoint: EndpointSpec, payload: bytes, output_dir: Path) -> None:
    rows.append(
        {
            'endpoint': endpoint.name,
            'filename': endpoint.filename,
            'bytes': str(len(payload)),
            'relative_path': str(Path(output_dir.name) / endpoint.filename),
        }
    )


def _write_manifest(output_dir: Path, rows: list[dict[str, str]]) -> None:
    manifest_path = output_dir / 'manifest.csv'
    with manifest_path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['endpoint', 'filename', 'bytes', 'relative_path'])
        writer.writeheader()
        writer.writerows(rows)


def _write_summary(output_dir: Path, *, api_base: str, channel_id: str, rows: list[dict[str, str]]) -> None:
    summary = {
        'status': 'ok',
        'collected_at_utc': datetime.now(timezone.utc).isoformat(),
        'api_base': api_base,
        'channel_id': channel_id,
        'files': rows,
    }
    (output_dir / 'collection-summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )


def main() -> None:
    api_base, _admin_token, _client_token, channel_id, output_dir = _load_runtime()
    manifest_rows: list[dict[str, str]] = []

    for endpoint in _build_endpoints(channel_id):
        payload = _request_bytes(api_base, endpoint)
        _write_file(output_dir / endpoint.filename, payload)
        _append_manifest_row(manifest_rows, endpoint=endpoint, payload=payload, output_dir=output_dir)

    _write_manifest(output_dir, manifest_rows)
    _write_summary(output_dir, api_base=api_base, channel_id=channel_id, rows=manifest_rows)
    print(
        json.dumps(
            {
                'status': 'ok',
                'output_dir': str(output_dir),
                'files_collected': len(manifest_rows),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == '__main__':
    main()
