from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AlertStateModel
from app.schemas.workspace import AlertItem

SHANGHAI = ZoneInfo("Asia/Shanghai")


def list_alerts_with_state(
    db: Session,
    alerts: list[AlertItem],
    *,
    unread_only: bool,
) -> list[AlertItem]:
    states = {
        state.alert_id: state
        for state in db.scalars(
            select(AlertStateModel).where(
                AlertStateModel.alert_id.in_([alert.id for alert in alerts])
            )
        )
    }
    resolved = [
        alert.model_copy(
            update={
                "is_read": states[alert.id].is_read if alert.id in states else alert.is_read,
            }
        )
        for alert in alerts
    ]
    return [item for item in resolved if not item.is_read] if unread_only else resolved


def set_alert_read_state(db: Session, alert_id: str, *, is_read: bool) -> bool:
    state = db.get(AlertStateModel, alert_id)
    now = datetime.now(SHANGHAI)
    if state is None:
        state = AlertStateModel(alert_id=alert_id, is_read=is_read, updated_at=now)
        db.add(state)
    else:
        state.is_read = is_read
        state.updated_at = now
    state.read_at = now if is_read else None
    db.commit()
    return state.is_read


def set_all_alerts_read(db: Session, alerts: list[AlertItem]) -> int:
    now = datetime.now(SHANGHAI)
    changed = 0
    for alert in alerts:
        state = db.get(AlertStateModel, alert.id)
        current_is_read = state.is_read if state is not None else alert.is_read
        if current_is_read:
            continue
        if state is None:
            db.add(
                AlertStateModel(
                    alert_id=alert.id,
                    is_read=True,
                    read_at=now,
                    updated_at=now,
                )
            )
        else:
            state.is_read = True
            state.read_at = now
            state.updated_at = now
        changed += 1
    db.commit()
    return changed
