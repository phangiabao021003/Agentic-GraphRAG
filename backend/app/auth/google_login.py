"""Resolve the local user for a verified Google identity (the only write path for it)."""
from app.db.users import (
    create_google_user,
    get_user_by_email,
    get_user_by_google_sub,
    set_google_sub,
)


async def find_or_create_google_user(pool, sub: str, email: str) -> dict:
    user = await get_user_by_google_sub(pool, sub)
    if user is not None:
        return user
    user = await get_user_by_email(pool, email)
    if user is not None:
        # Google verified this email, so it is the same person: link the account.
        await set_google_sub(pool, user["id"], sub)
        return {"id": user["id"], "email": user["email"]}
    return await create_google_user(pool, email, sub)
