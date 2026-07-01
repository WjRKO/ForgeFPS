import os
import json
import logging
from pywebpush import webpush, WebPushException

logger = logging.getLogger("boostpc.push")


def get_public_key() -> str:
    return os.environ.get("VAPID_PUBLIC_KEY", "")


def _claims():
    return {"sub": os.environ.get("VAPID_SUBJECT", "mailto:admin@example.com")}


async def send_push_to_user(db, user_id: str, payload: dict):
    """Send a web-push notification to all subscriptions of a user. Removes dead subscriptions."""
    private_key = os.environ.get("VAPID_PRIVATE_KEY", "")
    if not private_key:
        return
    subs = await db.push_subscriptions.find({"user_id": user_id}).to_list(50)
    for sub in subs:
        info = sub.get("subscription")
        try:
            webpush(subscription_info=info, data=json.dumps(payload),
                    vapid_private_key=private_key, vapid_claims=dict(_claims()))
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):
                await db.push_subscriptions.delete_one({"_id": sub["_id"]})
            else:
                logger.warning(f"Push failed: {e}")
        except Exception as e:
            logger.warning(f"Push error: {e}")
