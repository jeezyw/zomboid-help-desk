from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from .. import auth, config

router = APIRouter()


@router.get("/api/auth/status")
async def auth_status(request: Request):
    # Never gated by the SECURE_MODE middleware (see main.py) - the frontend needs
    # this to decide whether to show a login screen at all, before it has a session.
    token = request.cookies.get(auth.COOKIE_NAME)
    authenticated = (not config.SECURE_MODE) or auth.validate_session(token)
    return {"secure_mode": config.SECURE_MODE, "authenticated": authenticated}


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/api/auth/login")
async def login(body: LoginBody, request: Request, response: Response):
    ip = request.client.host if request.client else "unknown"
    remaining = auth.seconds_until_unlocked(ip)
    if remaining:
        raise HTTPException(429, f"Too many failed attempts - try again in {int(remaining) + 1}s.")

    if not auth.verify_credentials(body.username, body.password):
        auth.record_failure(ip)
        raise HTTPException(401, "Invalid username or password.")

    auth.record_success(ip)
    token = auth.create_session()
    response.set_cookie(
        auth.COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        max_age=auth.SESSION_TTL_DAYS * 24 * 3600,
    )
    return {"ok": True}


@router.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get(auth.COOKIE_NAME)
    if token:
        auth.delete_session(token)
    response.delete_cookie(auth.COOKIE_NAME)
    return {"ok": True}
