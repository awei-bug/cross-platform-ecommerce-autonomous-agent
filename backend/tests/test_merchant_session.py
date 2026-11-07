import copy
import traceback

import httpx
import pytest

from app.services.merchant_session import (
    MerchantSessionError,
    validate_merchant_session,
    validate_merchant_staff,
)


@pytest.fixture
def valid_payload():
    return {
        "status": 200,
        "data": {
            "user": {"id": 21, "tenant_id": 8},
            "tenant": {"id": 8, "slug": "demo", "status": 1},
            "permissions": {"is_super": False, "actions": ["product:read"]},
        },
    }


def test_reads_each_session_from_trusted_service(valid_payload):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json=valid_payload)

    transport = httpx.MockTransport(respond)
    result = validate_merchant_session(
        "http://127.0.0.1:5000", "merchant-token", transport=transport
    )
    assert (result.staff_id, result.tenant_id, result.tenant_slug) == (21, 8, "demo")
    assert result.actions == {"product:read"}
    assert calls[0].url.path == "/user/me/" and calls[0].headers["token"] == "merchant-token"
    valid_payload["data"]["permissions"]["actions"] = []
    assert not validate_merchant_session(
        "http://127.0.0.1:5000", "merchant-token", transport=transport
    ).actions
    assert len(calls) == 2


@pytest.mark.parametrize(
    "status,payload", [(200, {"status": 401}), (401, {}), (302, {}), (500, {})]
)
def test_rejects_denied_or_unavailable_sessions(status, payload):
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json=payload))
    with pytest.raises(MerchantSessionError):
        validate_merchant_session("http://127.0.0.1:5000", "secret-token", transport=transport)


@pytest.mark.parametrize(
    "mutation", ["wrong_tenant", "suspended", "missing_actions", "bad_super", "bad_id"]
)
def test_rejects_invalid_identity_or_permissions(valid_payload, mutation):
    payload = copy.deepcopy(valid_payload)
    data = payload["data"]
    if mutation == "wrong_tenant":
        data["user"]["tenant_id"] = 9
    elif mutation == "suspended":
        data["tenant"]["status"] = 0
    elif mutation == "missing_actions":
        del data["permissions"]["actions"]
    elif mutation == "bad_super":
        data["permissions"]["is_super"] = "true"
    else:
        data["user"]["id"] = True
    with pytest.raises(MerchantSessionError):
        validate_merchant_session(
            "http://localhost:5000",
            "token",
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)),
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://user:pass@example.com",
        "https://example.com/path",
        "https://example.com?token=x",
        "file:///tmp/x",
    ],
)
def test_invalid_service_config_does_not_send_token(url):
    def fail_if_called(request):
        pytest.fail("untrusted service must not receive the token")

    with pytest.raises(MerchantSessionError):
        validate_merchant_session(
            url, "secret-token", transport=httpx.MockTransport(fail_if_called)
        )


def test_network_failure_does_not_leak_token():
    token = "secret-token"

    def fail(request):
        raise httpx.ConnectError(token, request=request)

    with pytest.raises(MerchantSessionError) as caught:
        validate_merchant_session(
            "https://merchant.example", token, transport=httpx.MockTransport(fail)
        )
    assert token not in str(caught.value)
    assert token not in "".join(traceback.format_exception(caught.value))


def test_target_staff_is_checked_against_merchant_response():
    payload = {"status": 200, "data": {"id": 8, "tenant_id": 1}}
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(respond)
    validate_merchant_staff("http://127.0.0.1:5000", "token", 1, 8, transport=transport)
    assert requests[0].url.path == "/user/user/8/"
    payload["data"]["tenant_id"] = 2
    with pytest.raises(MerchantSessionError):
        validate_merchant_staff("http://127.0.0.1:5000", "token", 1, 8, transport=transport)
    payload["status"] = 404
    with pytest.raises(MerchantSessionError):
        validate_merchant_staff("http://127.0.0.1:5000", "token", 1, 8, transport=transport)
