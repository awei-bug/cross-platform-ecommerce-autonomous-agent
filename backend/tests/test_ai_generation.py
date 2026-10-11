import httpx
import pytest

from app.services import ai_generation
from app.services.ai_generation import AiGenerationError, generate_text
from app.services.ai_provider_registry import get_provider


class FakeClient:
    def __init__(self, response: httpx.Response):
        self.response = response
        self.requests: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url: str, **kwargs):
        self.requests.append({"url": url, **kwargs})
        return self.response


@pytest.mark.asyncio
async def test_openai_compatible_generation_normalizes_response(monkeypatch):
    fake = FakeClient(
        httpx.Response(
            200,
            json={"choices": [{"message": {"content": "  已生成候选文案  "}}]},
        )
    )
    monkeypatch.setattr(ai_generation.httpx, "AsyncClient", lambda **kwargs: fake)

    result = await generate_text(
        get_provider("openai"),
        "https://provider.test/v1",
        "sk-test-secret",
        "gpt-test",
        "生成春季商品文案",
        "copy",
    )

    assert result == "已生成候选文案"
    request = fake.requests[0]
    assert request["url"] == "https://provider.test/v1/chat/completions"
    assert request["headers"]["Authorization"] == "Bearer sk-test-secret"
    assert request["json"]["model"] == "gpt-test"
    assert request["json"]["messages"][-1]["content"] == "生成春季商品文案"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_id", "response_json", "expected"),
    [
        ("anthropic", {"content": [{"type": "text", "text": "Claude 候选"}]}, "Claude 候选"),
        (
            "gemini",
            {"candidates": [{"content": {"parts": [{"text": "Gemini 候选"}]}}]},
            "Gemini 候选",
        ),
        ("ollama", {"message": {"content": "Ollama 候选"}}, "Ollama 候选"),
    ],
)
async def test_generation_adapters_normalize_provider_payload(
    monkeypatch, provider_id, response_json, expected
):
    fake = FakeClient(httpx.Response(200, json=response_json))
    monkeypatch.setattr(ai_generation.httpx, "AsyncClient", lambda **kwargs: fake)

    result = await generate_text(
        get_provider(provider_id),
        "https://provider.test/api",
        "provider-secret" if provider_id != "ollama" else None,
        "model-test",
        "生成一版候选素材",
        "video_script",
    )

    assert result == expected
    assert fake.requests
    assert "provider-secret" not in str(fake.requests[0]["json"])


@pytest.mark.asyncio
async def test_openrouter_generation_sends_attribution_headers(monkeypatch):
    fake = FakeClient(
        httpx.Response(200, json={"choices": [{"message": {"content": "OpenRouter 候选"}}]})
    )
    monkeypatch.setattr(ai_generation.httpx, "AsyncClient", lambda **kwargs: fake)

    result = await generate_text(
        get_provider("openrouter"),
        "https://openrouter.ai/api/v1",
        "sk-or-secret",
        "openai/gpt-4o-mini",
        "生成春季商品文案",
        "copy",
    )

    assert result == "OpenRouter 候选"
    request = fake.requests[0]
    assert request["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert request["headers"]["Authorization"] == "Bearer sk-or-secret"
    assert request["headers"]["X-Title"]


@pytest.mark.asyncio
async def test_provider_error_does_not_leak_key(monkeypatch):
    secret = "sk-never-log-this"
    fake = FakeClient(httpx.Response(401, text=secret))
    monkeypatch.setattr(ai_generation.httpx, "AsyncClient", lambda **kwargs: fake)

    with pytest.raises(AiGenerationError) as exc_info:
        await generate_text(
            get_provider("openai"),
            "https://provider.test/v1",
            secret,
            "gpt-test",
            "生成文案",
            "copy",
        )

    assert secret not in str(exc_info.value)
    assert "HTTP 401" in str(exc_info.value)


@pytest.mark.asyncio
async def test_unauthorized_error_surfaces_vendor_message(monkeypatch):
    fake = FakeClient(
        httpx.Response(
            401, json={"error": {"message": "Missing Authentication header", "code": 401}}
        )
    )
    monkeypatch.setattr(ai_generation.httpx, "AsyncClient", lambda **kwargs: fake)

    with pytest.raises(AiGenerationError) as exc_info:
        await generate_text(
            get_provider("openai"),
            "https://provider.test/v1",
            "sk-test-secret",
            "gpt-test",
            "生成文案",
            "copy",
        )

    assert "Missing Authentication header" in str(exc_info.value)
    assert "sk-test-secret" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_unauthorized_error_never_echoes_credential_like_message(monkeypatch):
    fake = FakeClient(
        httpx.Response(401, json={"error": {"message": "invalid key sk-or-v1-abcdefgh"}})
    )
    monkeypatch.setattr(ai_generation.httpx, "AsyncClient", lambda **kwargs: fake)

    with pytest.raises(AiGenerationError) as exc_info:
        await generate_text(
            get_provider("openai"),
            "https://provider.test/v1",
            "sk-test-secret",
            "gpt-test",
            "生成文案",
            "copy",
        )

    assert "sk-or-v1" not in str(exc_info.value)
    assert "HTTP 401" in str(exc_info.value)


@pytest.mark.asyncio
async def test_image_generation_is_not_faked(monkeypatch):
    fake = FakeClient(httpx.Response(200, json={}))
    monkeypatch.setattr(ai_generation.httpx, "AsyncClient", lambda **kwargs: fake)

    with pytest.raises(AiGenerationError, match="图片文件生成尚未接入"):
        await generate_text(
            get_provider("openai"),
            "https://provider.test/v1",
            "sk-test",
            "gpt-image-test",
            "生成主图",
            "image",
        )
