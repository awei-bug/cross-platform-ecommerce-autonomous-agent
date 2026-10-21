"""素材平台质检与真实图片生成测试。"""

import io

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import get_settings
from app.main import app
from app.services import ai_image_generation
from app.services.ai_generation import AiGenerationError
from app.services.ai_provider_registry import get_provider


@pytest.fixture(scope="module")
def client(tmp_path_factory) -> TestClient:
    # 隔离素材存储目录：导出/上传文件只落临时目录，不污染 data/assets
    settings = get_settings()
    original_path = settings.asset_storage_local_path
    settings.asset_storage_local_path = str(tmp_path_factory.mktemp("assets"))
    with TestClient(app) as test_client:
        yield test_client
    settings.asset_storage_local_path = original_path


AUTH_HEADERS = {"Authorization": "Bearer demo-access-token"}


def _png(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "#88aaff").save(buffer, format="PNG")
    return buffer.getvalue()


def _upload(
    client: TestClient, content: bytes, content_type: str, filename: str, title: str
) -> dict:
    response = client.post(
        f"/api/v1/assets/uploads?title={title}",
        content=content,
        headers={
            **AUTH_HEADERS,
            "Content-Type": content_type,
            "X-Filename": filename,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------- 上传质检


def test_compliant_image_passes_platform_size_check(client: TestClient) -> None:
    asset = _upload(client, _png(800, 800), "image/png", "hero.png", "合规主图")
    version = asset["versions"][0]
    assert version["quality_status"] == "passed"
    assert version["object_key"]


def test_small_image_is_flagged_by_platform_rules(client: TestClient) -> None:
    asset = _upload(client, _png(100, 100), "image/png", "small.png", "过小主图")
    version = asset["versions"][0]
    assert version["quality_status"] == "warning"
    issues = version["quality_issues"]
    assert any("尺寸" in item or "低于" in item or "1:1" in item for item in issues)


def test_sensitive_words_are_flagged(client: TestClient) -> None:
    asset = _upload(
        client,
        "本产品全网最低，绝对有效，纯天然配方".encode(),
        "text/plain",
        "copy.txt",
        "夸大文案",
    )
    version = asset["versions"][0]
    assert version["quality_status"] == "warning"
    assert any("全网最低" in item for item in version["quality_issues"])


def test_clean_copy_passes_sensitive_word_check(client: TestClient) -> None:
    asset = _upload(
        client,
        "温和配方，适合日常保湿使用，请在耳后测试后使用".encode(),
        "text/plain",
        "clean.txt",
        "规范文案",
    )
    version = asset["versions"][0]
    assert version["quality_status"] == "passed"


def test_quality_recheck_endpoint(client: TestClient) -> None:
    asset = _upload(client, _png(100, 100), "image/png", "recheck.png", "重检主图")
    version_id = asset["versions"][0]["id"]
    response = client.post(
        f"/api/v1/assets/versions/{version_id}/quality-checks", headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["quality_status"] == "warning"
    check_types = {item["check_type"] for item in payload["checks"]}
    assert {"platform_size", "sensitive_words", "copyright"} <= check_types
    # 版权检查占位：不做结论，不冒充通过
    copyright_check = next(
        item for item in payload["checks"] if item["check_type"] == "copyright"
    )
    assert copyright_check["status"] == "skipped"

    missing = client.post(
        "/api/v1/assets/versions/assetver-missing/quality-checks", headers=AUTH_HEADERS
    )
    assert missing.status_code == 404


# ---------------------------------------------------------------- 图片生成适配器


class FakeImageClient:
    """按 URL 分派响应的假客户端，支持 POST（生成）与 GET（下载）。"""

    def __init__(self, post_response: httpx.Response, get_response: httpx.Response | None = None):
        self.post_response = post_response
        self.get_response = get_response
        self.requests: list[tuple[str, str]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url: str, **kwargs):
        self.requests.append(("POST", url))
        return self.post_response

    async def get(self, url: str, **kwargs):
        self.requests.append(("GET", url))
        return self.get_response or httpx.Response(404)


@pytest.mark.asyncio
async def test_generate_image_returns_b64_bytes(monkeypatch) -> None:
    import base64

    png = _png(64, 64)
    fake = FakeImageClient(
        httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(png).decode()}]})
    )
    monkeypatch.setattr(ai_image_generation.httpx, "AsyncClient", lambda **kwargs: fake)

    content = await ai_image_generation.generate_image(
        get_provider("openai"),
        "https://provider.test/v1",
        "sk-test",
        "gpt-image-1",
        "生成商品主图",
    )
    assert content == png
    method, url = fake.requests[0]
    assert method == "POST"
    assert url == "https://provider.test/v1/images/generations"


@pytest.mark.asyncio
async def test_generate_image_downloads_url_result(monkeypatch) -> None:
    png = _png(64, 64)
    fake = FakeImageClient(
        httpx.Response(200, json={"data": [{"url": "https://cdn.test/img.png"}]}),
        get_response=httpx.Response(200, content=png),
    )
    monkeypatch.setattr(ai_image_generation.httpx, "AsyncClient", lambda **kwargs: fake)

    content = await ai_image_generation.generate_image(
        get_provider("openai"), "https://provider.test/v1", "sk-test", "gpt-image-1", "主图"
    )
    assert content == png
    assert ("GET", "https://cdn.test/img.png") in fake.requests


@pytest.mark.asyncio
async def test_generate_image_rejects_unsupported_protocol() -> None:
    with pytest.raises(AiGenerationError, match="图片生成适配器"):
        await ai_image_generation.generate_image(
            get_provider("anthropic"),
            "https://provider.test",
            "sk-test",
            "claude",
            "主图",
        )


# ---------------------------------------------------------------- 生成任务真实图片链路


@pytest.fixture
def live_generation(tmp_path, monkeypatch):
    """打开 AI_LIVE 开关并隔离素材目录。"""
    monkeypatch.setenv("AI_LIVE_GENERATION_ENABLED", "true")
    monkeypatch.setenv("ASSET_STORAGE_LOCAL_PATH", str(tmp_path / "assets"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_generation_job_image_live_path(client: TestClient, live_generation, monkeypatch) -> None:
    """真实图片生成链路：生成 → 落存储 → 质检（尺寸不达标给 warning）。"""
    from app.db.models import AssetVersionModel
    from app.db.session import session_scope

    # 准备一个启用的 AI 配置
    configuration = client.post(
        "/api/v1/ai/configurations",
        json={
            "provider_id": "openai",
            "display_name": "图片生成测试配置",
            "api_key": "sk-test-image-key",
            "selected_model": "gpt-image-1",
        },
        headers=AUTH_HEADERS,
    )
    assert configuration.status_code == 201, configuration.text
    configuration_id = configuration.json()["id"]

    async def fake_generate_image(*args, **kwargs) -> bytes:
        return _png(200, 200)  # 小于全部平台最小尺寸，触发尺寸 warning

    monkeypatch.setattr(
        "app.services.asset_repository.generate_image", fake_generate_image
    )

    created = client.post(
        "/api/v1/assets/generation-jobs",
        json={
            "asset_type": "image",
            "prompt": "生成一张清爽的保湿面霜主图",
            "configuration_id": configuration_id,
            "model_id": "gpt-image-1",
        },
        headers=AUTH_HEADERS,
    )
    assert created.status_code == 202, created.text
    job_id = created.json()["id"]

    # eager 模式：任务已同步执行完毕，读取终态
    job = client.get(f"/api/v1/assets/generation-jobs/{job_id}", headers=AUTH_HEADERS)
    assert job.status_code == 200
    job_payload = job.json()
    assert job_payload["status"] == "succeeded", job_payload.get("error_message")
    assert job_payload["is_demo"] is False
    version_id = job_payload["result_version_id"]
    assert version_id

    # 校验版本与质检结果
    with session_scope() as db:
        version = db.get(AssetVersionModel, version_id)
        assert version is not None
        assert version.object_key, "真实生成必须落对象存储"
        assert version.content_type == "image/png"
        assert version.quality_status == "warning"
        assert version.source == "ai"
