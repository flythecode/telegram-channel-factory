from urllib import error

import pytest

from app.core.config import settings
from app.services.llm_provider import (
    AnthropicAdapter,
    GeminiAdapter,
    LLMCircuitBreakerOpenError,
    LLMGenerationRequest,
    LLMProviderError,
    OpenAIAdapter,
    OpenRouterAdapter,
    StubLLMAdapter,
    generate_with_failover,
    reset_llm_circuit_breakers,
)


class Headers(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class FakeHTTPResponse:
    def __init__(self, payload: str, headers: dict | None = None):
        self.payload = payload.encode('utf-8')
        self.headers = Headers(headers or {'x-request-id': 'req-123'})

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture(autouse=True)
def _reset_circuit_breakers():
    reset_llm_circuit_breakers()
    yield
    reset_llm_circuit_breakers()


def test_stub_adapter_returns_normalized_result():
    result = StubLLMAdapter().generate(
        LLMGenerationRequest(system_prompt='system', user_prompt='Write about BTC')
    )

    assert result.provider == 'stub'
    assert result.output_text
    assert result.finish_reason == 'stop'
    assert result.request_id == 'stub-request'
    assert result.latency_ms >= 1


@pytest.mark.parametrize(
    ('adapter', 'response_json', 'header_key', 'expected_text', 'expected_prompt_tokens', 'expected_completion_tokens'),
    [
        (
            OpenAIAdapter(),
            {
                'id': 'chatcmpl-1',
                'model': 'gpt-4.1-mini',
                'choices': [{'message': {'content': 'OpenAI text'}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 11, 'completion_tokens': 22, 'total_tokens': 33},
            },
            'x-request-id',
            'OpenAI text',
            11,
            22,
        ),
        (
            OpenRouterAdapter(),
            {
                'id': 'or-1',
                'model': 'openrouter/model',
                'choices': [{'message': {'content': 'OpenRouter text'}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 4, 'completion_tokens': 5, 'total_tokens': 9},
            },
            'x-request-id',
            'OpenRouter text',
            4,
            5,
        ),
        (
            AnthropicAdapter(),
            {
                'id': 'msg_1',
                'model': 'claude-3-5-sonnet',
                'content': [{'type': 'text', 'text': 'Anthropic text'}],
                'stop_reason': 'end_turn',
                'usage': {'input_tokens': 7, 'output_tokens': 8},
            },
            'request-id',
            'Anthropic text',
            7,
            8,
        ),
        (
            GeminiAdapter(),
            {
                'responseId': 'gem-1',
                'candidates': [
                    {'content': {'parts': [{'text': 'Gemini text'}]}, 'finishReason': 'STOP'}
                ],
                'usageMetadata': {
                    'promptTokenCount': 13,
                    'candidatesTokenCount': 21,
                    'totalTokenCount': 34,
                },
            },
            'x-request-id',
            'Gemini text',
            13,
            21,
        ),
    ],
)
def test_provider_parsers_return_normalized_shapes(
    adapter,
    response_json,
    header_key,
    expected_text,
    expected_prompt_tokens,
    expected_completion_tokens,
):
    result = adapter.parse_response(response_json, Headers({header_key: 'req-123'}), latency_ms=42)

    assert result.output_text == expected_text
    assert result.request_id == 'req-123'
    assert result.prompt_tokens == expected_prompt_tokens
    assert result.completion_tokens == expected_completion_tokens
    assert result.latency_ms == 42


def test_openai_adapter_retries_retryable_http_errors(monkeypatch):
    monkeypatch.setattr(settings, 'llm_max_retries', 2)
    monkeypatch.setattr(settings, 'llm_retry_base_delay_ms', 1)
    monkeypatch.setattr(settings, 'llm_retry_max_delay_ms', 2)
    monkeypatch.setattr('app.services.llm_provider.random.uniform', lambda a, b: 0.0)

    attempts = {'count': 0}
    sleeps: list[float] = []

    def fake_sleep(delay: float):
        sleeps.append(delay)

    def fake_urlopen(req, timeout):
        attempts['count'] += 1
        if attempts['count'] < 3:
            raise error.HTTPError(req.full_url, 429, 'rate limit', hdrs=None, fp=None)
        return FakeHTTPResponse(
            '{"id":"chatcmpl-1","model":"gpt-4.1-mini","choices":[{"message":{"content":"Recovered"},"finish_reason":"stop"}],"usage":{"prompt_tokens":1,"completion_tokens":2,"total_tokens":3}}'
        )

    monkeypatch.setattr('app.services.llm_provider.time.sleep', fake_sleep)
    monkeypatch.setattr('app.services.llm_provider.request.urlopen', fake_urlopen)

    result = OpenAIAdapter(api_key='test-key').generate(
        LLMGenerationRequest(system_prompt='system', user_prompt='hello')
    )

    assert result.output_text == 'Recovered'
    assert attempts['count'] == 3
    assert sleeps == [0.001, 0.002]


def test_openai_adapter_does_not_retry_non_retryable_http_errors(monkeypatch):
    monkeypatch.setattr(settings, 'llm_max_retries', 3)

    def fake_urlopen(req, timeout):
        raise error.HTTPError(req.full_url, 400, 'bad request', hdrs=None, fp=None)

    monkeypatch.setattr('app.services.llm_provider.request.urlopen', fake_urlopen)

    with pytest.raises(LLMProviderError) as exc_info:
        OpenAIAdapter(api_key='test-key').generate(
            LLMGenerationRequest(system_prompt='system', user_prompt='hello')
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.retryable is False


def test_openai_adapter_opens_circuit_breaker_after_repeated_retryable_failures(monkeypatch):
    monkeypatch.setattr(settings, 'llm_max_retries', 0)
    monkeypatch.setattr(settings, 'llm_circuit_breaker_threshold', 2)
    monkeypatch.setattr(settings, 'llm_circuit_breaker_cooldown_seconds', 30)

    now = {'value': 1000.0}

    def fake_time():
        return now['value']

    def fake_urlopen(req, timeout):
        raise error.URLError('provider down')

    monkeypatch.setattr('app.services.llm_provider.time.time', fake_time)
    monkeypatch.setattr('app.services.llm_provider.request.urlopen', fake_urlopen)

    adapter = OpenAIAdapter(api_key='test-key')
    for _ in range(2):
        with pytest.raises(LLMProviderError):
            adapter.generate(LLMGenerationRequest(system_prompt='system', user_prompt='hello'))

    with pytest.raises(LLMCircuitBreakerOpenError):
        adapter.generate(LLMGenerationRequest(system_prompt='system', user_prompt='hello again'))

    now['value'] += 31
    with pytest.raises(LLMProviderError):
        adapter.generate(LLMGenerationRequest(system_prompt='system', user_prompt='after cooldown'))


def test_generate_with_failover_uses_fallback_provider_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, 'llm_provider', 'openai')
    monkeypatch.setattr(settings, 'llm_model_default', 'gpt-4.1-mini')
    monkeypatch.setattr(settings, 'llm_failover_strategy', 'fallback-provider')
    monkeypatch.setattr(settings, 'llm_fallback_provider', 'stub')
    monkeypatch.setattr(settings, 'llm_fallback_model', 'stub-fallback')

    def primary_generate(self, payload):
        raise LLMProviderError('primary down', provider='openai', retryable=True)

    monkeypatch.setattr(OpenAIAdapter, 'generate', primary_generate)

    result = generate_with_failover(
        LLMGenerationRequest(system_prompt='system', user_prompt='hello from fallback')
    )

    assert result.provider == 'stub'
    assert result.model == 'stub-fallback'
    assert result.failover is not None
    assert result.failover['outcome'] == 'fallback-provider-succeeded'
    assert result.failover['fallback_provider'] == 'stub'


def test_generate_with_failover_returns_graceful_degradation_when_primary_unavailable(monkeypatch):
    monkeypatch.setattr(settings, 'llm_provider', 'openai')
    monkeypatch.setattr(settings, 'llm_model_default', 'gpt-4.1-mini')
    monkeypatch.setattr(settings, 'llm_failover_strategy', 'graceful-degradation')
    monkeypatch.setattr(settings, 'llm_fallback_provider', None)
    monkeypatch.setattr(settings, 'llm_fallback_model', None)

    def primary_generate(self, payload):
        raise LLMProviderError('provider outage', provider='openai', retryable=True)

    monkeypatch.setattr(OpenAIAdapter, 'generate', primary_generate)

    result = generate_with_failover(
        LLMGenerationRequest(system_prompt='system', user_prompt='hello degradation')
    )

    assert result.provider == 'openai'
    assert result.finish_reason == 'provider_unavailable'
    assert result.output_text == ''
    assert result.failover is not None
    assert result.failover['outcome'] == 'graceful-degradation'
    assert result.failover['primary_error']['message'] == 'provider outage'
