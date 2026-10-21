"""淘宝客数据源契约测试（签名、解析、路由准入）。

全部使用 httpx.MockTransport 拦截网络，无需真实 AppKey 或调用阿里妈妈网关。
"""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.integrations.taobao import (
    TaobaokeApiError,
    TaobaokeClient,
    parse_materials,
    sign_top_request,
)


def test_sign_top_request_is_md5_uppercase() -> None:
    # 与抖店不同：淘宝在首尾都包 secret
    signature = sign_top_request(
        {"method": "taobao.tbk.dg.material.optional", "app_key": "k", "q": "精华"}, "secret"
    )
    assert len(signature) == 32
    assert signature.isupper()


def test_parse_materials_extracts_items() -> None:
    payload = {
        "tbk_dg_material_optional_response": {
            "result_list": {
                "map_data": [
                    {
                        "item_id": "620012",
                        "title": "玻尿酸保湿精华",
                        "zk_final_price": "129.00",
                        "reserve_price": "159.00",
                        "volume": "8200",
                        "commission_rate": "1500",
                        "shop_title": "某旗舰店",
                        "category_name": "美容护肤",
                        "user_type": "1",
                        "item_url": "https://item.test/x",
                    }
                ]
            }
        }
    }
    materials = parse_materials(payload)
    assert len(materials) == 1
    item = materials[0]
    assert item.item_id == "620012"
    assert item.price == 129.0
    assert item.is_tmall is True
    assert item.sales_volume == 8200
    assert item.commission_rate == 15.0  # 万分位折算为百分比


def test_parse_materials_raises_on_error_response() -> None:
    with pytest.raises(TaobaokeApiError):
        parse_materials({"error_response": {"code": 11, "sub_msg": "权限不足"}})


def _build_client(handler) -> TaobaokeClient:
    return TaobaokeClient(
        app_key="tb-key",
        app_secret="tb-secret",
        adzone_id="123456",
        api_base_url="https://eco.taobao.com/router/rest",
        transport=httpx.MockTransport(handler),
    )


def test_search_materials_calls_gateway_and_parses() -> None:
    import urllib.parse

    def handler(request: httpx.Request) -> httpx.Response:
        body = dict(urllib.parse.parse_qsl(request.content.decode()))
        assert body.get("method") == "taobao.tbk.dg.material.optional"
        return httpx.Response(
            200,
            json={
                "tbk_dg_material_optional_response": {
                    "result_list": {
                    "map_data": [
                        {"item_id": "1", "title": "测试商品", "zk_final_price": "9.9"}
                    ]
                }
                }
            },
        )

    client = _build_client(handler)
    import asyncio

    materials = asyncio.run(client.search_materials(keyword="测试"))
    assert materials[0].title == "测试商品"


@pytest.fixture(scope="module")
def client() -> TestClient:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def test_import_route_requires_credentials(client: TestClient) -> None:
    response = client.post(
        "/api/v1/agent/competitors/import-taobaoke",
        headers={"Authorization": "Bearer demo-access-token"},
        json={"keyword": "精华", "limit": 5},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "taobaoke_credentials_required"
