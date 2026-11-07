"""云购订单事件消费器的契约测试。

覆盖 fail-closed 配置、event_id 幂等、水位推进、未激活租户丢弃。
"""
import json
from unittest.mock import patch

from sqlalchemy import select

from app.core.config import Settings
from app.db.models import (
    EventWatermarkModel,
    MerchantOrganizationMappingModel,
    OrderProjectionModel,
)
from app.db.session import initialize_database, session_scope
from app.services.order_event_consumer import consume_once, events_configured

URL = "http://127.0.0.1:5000/api/events"


def _settings(**overrides) -> Settings:
    base = {
        "events_enabled": True,
        "events_url": URL,
        "events_token": "test-token",
    }
    base.update(overrides)
    return Settings(**base)


def _event(event_id=1, tenant_id=1, order_no="O1") -> dict:
    return {
        "id": event_id,
        "tenant_id": tenant_id,
        "event_type": "order.created",
        "aggregate_type": "order",
        "aggregate_id": str(event_id),
        "occurred_at": "2026-11-07T15:00:00+08:00",
        "payload": json.dumps({
            "order_no": order_no,
            "status": "pending_pay",
            "price": 88.0,
            "number": 2,
            "item_title": "云购测试商品",
            "sku": "SKU-1",
        }),
    }


def _reset(db, *, tenant_id=1, active=True) -> None:
    db.query(OrderProjectionModel).delete()
    db.query(EventWatermarkModel).delete()
    db.query(MerchantOrganizationMappingModel).delete()
    db.add(
        MerchantOrganizationMappingModel(
            tenant_id=tenant_id, organization_id="org-a", is_active=active
        )
    )
    db.commit()


def test_events_configured_fails_closed() -> None:
    assert not events_configured(_settings(events_enabled=False))
    assert not events_configured(_settings(events_url=None))
    assert not events_configured(_settings(events_token=None))
    assert not events_configured(_settings(events_url="file:///etc/passwd"))
    assert events_configured(_settings())


def test_consume_once_is_idempotent_and_advances_watermark() -> None:
    initialize_database()
    with session_scope() as db:
        _reset(db)

    payload = {"events": [_event()], "next_cursor": 1, "has_more": False}
    with patch("app.services.order_event_consumer._fetch_events", return_value=payload):
        first = consume_once(_settings())
        second = consume_once(_settings())

    assert first["inserted"] == 1
    assert second["inserted"] == 0
    assert second["skipped"] == 1
    assert second["watermark"] == 1

    with session_scope() as db:
        rows = list(db.scalars(select(OrderProjectionModel)))
        assert len(rows) == 1
        assert rows[0].event_id == 1
        assert rows[0].source == "event"
        assert rows[0].is_demo is False
        assert rows[0].payload["order_no"] == "O1"
        assert rows[0].payload["platform"] == "yungou"
        assert rows[0].organization_id == "org-a"


def test_inactive_tenant_event_is_dropped_but_watermark_advances() -> None:
    initialize_database()
    with session_scope() as db:
        _reset(db, active=False)

    payload = {"events": [_event(event_id=5)], "next_cursor": 5, "has_more": False}
    with patch("app.services.order_event_consumer._fetch_events", return_value=payload):
        result = consume_once(_settings())

    assert result["inserted"] == 0
    assert result["skipped"] == 1
    assert result["watermark"] == 5

    with session_scope() as db:
        assert db.scalars(select(OrderProjectionModel)).all() == []
