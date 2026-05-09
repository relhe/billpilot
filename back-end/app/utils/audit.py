from datetime import datetime, timezone
from typing import Literal

AuditAction = Literal["create", "update", "delete", "upload_evidence"]


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
            "diff": diff,
        }
    )
