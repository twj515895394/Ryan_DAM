from __future__ import annotations

import json
import httpx
import pytest

from backend.app.services.ai.protocol_poc import (
    CAPABILITY_IMAGE_EDIT,
    CAPABILITY_IMAGE_GENERATE,
    CAPABILITY_IMAGE_UNDERSTAND,
    CAPABILITY_TEXT_OPTIMIZE,
    normalize_base_url,
    parse_error_response,
    probe_all_capabilities,
    probe_image_edit,
    probe_image_generate,
    probe_image_understand,
    probe_text_optimize,
)


def test_normalize_base_url():
    assert normalize_base_url("https://api.openai.com/v1/") == "https://api.openai.com/v1"
    assert normalize_base_url("http://127.0.0.1:8000 ") == "http://127.0.0.1:8000"


def test_parse_error_response():
    code, msg = parse_error_response(401, '{"error": {"message": "Invalid API Key", "code": "invalid_api_key"}}')
    assert code == "unauthorized"
    assert "API Key" in msg

    code, msg = parse_error_response(404, '{"error": {"message": "The model gpt-5 does not exist"}}')
    assert code == "model_not_found"

    code, msg = parse_error_response(404, '{"error": {"message": "Endpoint not found"}}')
    assert code == "capability_unsupported"

    code, msg = parse_error_response(429, '{"error": {"message": "Rate limit reached"}}')
    assert code == "rate_limit"


def test_probe_text_optimize_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.test.com/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        data = json.loads(request.content)
        assert data["model"] == "gpt-4o-mini"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "ok"}}]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    res = probe_text_optimize(client, "https://api.test.com/v1", "test-key", "gpt-4o-mini")
    assert res.supported is True
    assert res.capability == CAPABILITY_TEXT_OPTIMIZE
    assert res.output_sample == "ok"


def test_probe_image_understand_success_and_unsupported():
    # Success mock
    def success_handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.test.com/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "A white square"}}]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(success_handler))
    res = probe_image_understand(client, "https://api.test.com/v1", "test-key", "gpt-4o")
    assert res.supported is True
    assert res.capability == CAPABILITY_IMAGE_UNDERSTAND
    assert res.output_sample == "A white square"

    # Unsupported mock (e.g. text-only model returning 400 with vision error)
    def unsupported_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": {"message": "This model does not support image input."}},
        )

    client_unsupp = httpx.Client(transport=httpx.MockTransport(unsupported_handler))
    res_unsupp = probe_image_understand(client_unsupp, "https://api.test.com/v1", "test-key", "gpt-3.5-turbo")
    assert res_unsupp.supported is False
    assert res_unsupp.error_code == "capability_unsupported"


def test_probe_image_generate_success_and_404():
    def gen_handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.test.com/v1/images/generations"
        return httpx.Response(
            200,
            json={
                "data": [{"url": "https://images.test.com/output.png"}]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(gen_handler))
    res = probe_image_generate(client, "https://api.test.com/v1", "test-key", "dall-e-3")
    assert res.supported is True
    assert res.capability == CAPABILITY_IMAGE_GENERATE
    assert "https://images.test.com/output.png" in (res.output_sample or "")

    # Provider doesn't implement image generation
    def not_found_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Not Found")

    client_404 = httpx.Client(transport=httpx.MockTransport(not_found_handler))
    res_404 = probe_image_generate(client_404, "https://api.test.com/v1", "test-key", "chat-only-model")
    assert res_404.supported is False
    assert res_404.error_code == "capability_unsupported"

    # Gemini chat route generation with markdown response
    def gemini_handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.test.com/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "choices": [{
                    "message": {
                        "content": "Here is your image: ![gen](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==)"
                    }
                }]
            },
        )

    client_gemini = httpx.Client(transport=httpx.MockTransport(gemini_handler))
    res_gemini = probe_image_generate(client_gemini, "https://api.test.com/v1", "test-key", "gemini-3.1-flash-image")
    assert res_gemini.supported is True
    assert "data:image/png;base64" in (res_gemini.output_sample or "")


def test_probe_image_edit_success_and_timeout():
    def edit_handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.test.com/v1/images/edits"
        assert "multipart/form-data" in request.headers.get("content-type", "")
        return httpx.Response(
            200,
            json={
                "data": [{"url": "https://images.test.com/edited.png"}]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(edit_handler))
    res = probe_image_edit(client, "https://api.test.com/v1", "test-key", "dall-e-2")
    assert res.supported is True
    assert res.capability == CAPABILITY_IMAGE_EDIT

    # Timeout
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Connection timed out")

    client_timeout = httpx.Client(transport=httpx.MockTransport(timeout_handler))
    res_timeout = probe_image_edit(client_timeout, "https://api.test.com/v1", "test-key", "dall-e-2")
    assert res_timeout.supported is False
    assert res_timeout.error_code == "timeout"


def test_probe_all_capabilities():
    def combined_handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/chat/completions" in path:
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
        if "/images/generations" in path:
            return httpx.Response(200, json={"data": [{"url": "http://img.png"}]})
        if "/images/edits" in path:
            return httpx.Response(404, text="No edit endpoint")
        return httpx.Response(400, text="Bad request")

    client = httpx.Client(transport=httpx.MockTransport(combined_handler))
    mapping = {
        CAPABILITY_TEXT_OPTIMIZE: "gpt-4o-mini",
        CAPABILITY_IMAGE_UNDERSTAND: "gpt-4o",
        CAPABILITY_IMAGE_GENERATE: "dall-e-3",
        CAPABILITY_IMAGE_EDIT: "dall-e-2",
    }
    results = probe_all_capabilities(client, "https://api.test.com/v1", "test-key", mapping)
    assert len(results) == 4
    assert results[CAPABILITY_TEXT_OPTIMIZE].supported is True
    assert results[CAPABILITY_IMAGE_UNDERSTAND].supported is True
    assert results[CAPABILITY_IMAGE_GENERATE].supported is True
    assert results[CAPABILITY_IMAGE_EDIT].supported is False
    assert results[CAPABILITY_IMAGE_EDIT].error_code == "capability_unsupported"
