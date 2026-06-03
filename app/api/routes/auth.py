from fastapi import APIRouter, Depends, HTTPException, Form, Response, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.user import User
from app.core.auth import (
    verify_password,
    create_access_token,
    blacklist_token,
    get_token_expiry,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter()


@router.get("/login", response_class=HTMLResponse, summary="Login page")
def login_page(request: Request):
    """Renders the dashboard login page."""
    # If the user is already logged in, redirect them to the home dashboard
    token = request.cookies.get("access_token")
    if token:
        try:
            from jose import jwt
            from app.core.auth import ALGORITHM, settings
            payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
            if payload.get("sub"):
                return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        except Exception:
            pass

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="pages/login.html",
        context={"title": "Login"},
    )


@router.post("/auth/login", summary="Validate credentials and issue JWT")
async def login(
    request: Request,
    response: Response,
    db: Session = Depends(get_db_session)
):
    """
    Validates username and password and returns a JWT access token.
    Sets the access_token cookie for browser-based navigation.
    Supports both application/json and application/x-www-form-urlencoded.
    """
    content_type = request.headers.get("content-type", "")
    username = None
    password = None

    if "application/json" in content_type:
        try:
            body = await request.json()
            username = body.get("username")
            password = body.get("password")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
    else:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    # Fetch user from DB
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Generate JWT access token
    token = create_access_token(data={"sub": user.username})

    # Set secure HTTPOnly cookie for seamless Jinja2 page loads
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False,  # Set True in production over HTTPS
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username
    }


@router.post("/auth/logout", summary="Logout and blacklist token")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db_session)
):
    """Logs out the user by blacklisting their current token and deleting their cookie."""
    token = None
    auth_header = request.headers.get("Authorization")
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        token = request.cookies.get("access_token")

    if token:
        expires_at = get_token_expiry(token)
        blacklist_token(db, token, expires_at)

    response.delete_cookie("access_token")
    return {"success": True, "detail": "Logged out successfully"}


@router.get("/logout", summary="Logout redirect helper for browser anchor tags")
def logout_redirect(
    request: Request,
    response: Response,
    db: Session = Depends(get_db_session)
):
    """Redirect endpoint that clears cookies and blacklists the token on browser logout."""
    token = request.cookies.get("access_token")
    if token:
        expires_at = get_token_expiry(token)
        blacklist_token(db, token, expires_at)

    response.delete_cookie("access_token")
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
