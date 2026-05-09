from datetime import date, datetime, timezone
from typing import Literal

AuditAction = Literal["create", "update", "delete", "upload_evidence"]


def _make_bson_safe(obj):
    """Recursively convert non-BSON-encodable types (e.g. date) to strings."""
    if isinstance(obj, dict):
        return {k: _make_bson_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_bson_safe(i) for i in obj]
    if isinstance(obj, date) and not isinstance(obj, datetime):
        return obj.isoformat()
    return obj


async def write_audit_entry(
    *,
    db,
    collection: str,
    user_id: str,
    action: AuditAction,
    payment_id: str,
    diff: dict,
) -> None:
    await db[collection].insert_one(
        {
            "timestamp": datetime.now(timezone.utc),
            "user_id": user_id,
            "action": action,
            "payment_id": payment_id,
            "diff": _make_bson_safe(diff),
        }
    )
