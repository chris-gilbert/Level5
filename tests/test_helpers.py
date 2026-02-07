"""Tests for helper functions in main.py."""

from unittest.mock import MagicMock

from level5.proxy.main import (
    _build_upstream_headers,
    _calculate_cost_usdc,
    _mock_anthropic_sse_body,
    _mock_openai_sse_body,
    _parse_anthropic_sse_usage,
    _parse_openai_sse_usage,
)


def test_calculate_cost_known_model():
    usage = {"input_tokens": 1000, "output_tokens": 1000}
    cost = _calculate_cost_usdc(usage, "claude-sonnet-4-5-20250929")
    # input: 1000 * 3000/1000 = 3000, output: 1000 * 15000/1000 = 15000
    assert cost == 18000


def test_calculate_cost_unknown_model():
    usage = {"input_tokens": 1000, "output_tokens": 1000}
    cost = _calculate_cost_usdc(usage, "unknown-model-xyz")
    # default: input 5000, output 15000 per 1k
    assert cost == 20000


def test_parse_anthropic_sse_usage():
    events = [
        {"type": "message_start", "message": {"usage": {"input_tokens": 42}}},
        {"type": "content_block_delta", "delta": {"text": "hi"}},
        {"type": "message_delta", "usage": {"output_tokens": 99}},
    ]
    usage = _parse_anthropic_sse_usage(events)
    assert usage == {"input_tokens": 42, "output_tokens": 99}


def test_parse_anthropic_sse_usage_empty():
    assert _parse_anthropic_sse_usage([]) == {"input_tokens": 0, "output_tokens": 0}


def test_parse_openai_sse_usage():
    events = [
        {"choices": [{"delta": {"content": "hi"}}]},
        {"choices": [{"delta": {}}], "usage": {"prompt_tokens": 10, "completion_tokens": 20}},
    ]
    usage = _parse_openai_sse_usage(events)
    assert usage == {"input_tokens": 10, "output_tokens": 20}


def test_parse_openai_sse_usage_no_usage():
    events = [{"choices": [{"delta": {"content": "hi"}}]}]
    usage = _parse_openai_sse_usage(events)
    assert usage == {"input_tokens": 0, "output_tokens": 0}


def test_build_upstream_headers_openai():
    mock_request = MagicMock()
    mock_request.headers = {}
    headers = _build_upstream_headers(
        "https://api.openai.com/v1/chat/completions",
        "sk-test-key",
        mock_request,
    )
    assert headers["Authorization"] == "Bearer sk-test-key"
    assert "x-api-key" not in headers


def test_build_upstream_headers_anthropic():
    mock_request = MagicMock()
    mock_request.headers = {"anthropic-version": "2024-01-01"}
    headers = _build_upstream_headers(
        "https://api.anthropic.com/v1/messages",
        "ant-test-key",
        mock_request,
    )
    assert headers["x-api-key"] == "ant-test-key"
    assert headers["anthropic-version"] == "2024-01-01"
    assert "Authorization" not in headers


def test_build_upstream_headers_anthropic_default_version():
    mock_request = MagicMock()
    mock_request.headers = {}
    headers = _build_upstream_headers(
        "https://api.anthropic.com/v1/messages",
        "ant-test-key",
        mock_request,
    )
    assert headers["anthropic-version"] == "2023-06-01"


def test_build_upstream_headers_forwards_anthropic_beta():
    mock_request = MagicMock()
    mock_request.headers = {
        "anthropic-version": "2025-01-01",
        "anthropic-beta": "context-management-2025-01-01",
    }
    headers = _build_upstream_headers(
        "https://api.anthropic.com/v1/messages",
        "ant-test-key",
        mock_request,
    )
    assert headers["anthropic-version"] == "2025-01-01"
    assert headers["anthropic-beta"] == "context-management-2025-01-01"


def test_mock_anthropic_sse_body_format():
    body = _mock_anthropic_sse_body()
    assert "event: message_start" in body
    assert "event: message_delta" in body
    assert "data: " in body


def test_mock_openai_sse_body_format():
    body = _mock_openai_sse_body()
    assert "data: " in body
    assert "[DONE]" in body
