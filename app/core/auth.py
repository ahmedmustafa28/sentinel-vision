from datetime import datetime, timedelta, timezone
from fastapi import Depends, Request, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import PyJWTError as JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.user import User, BlacklistedToken

# Initialize password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Use OAuth2PasswordBearer but allow auto_error=False since we also fallback to cookie
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

settings = get_settings()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


class UnauthenticatedException(Exception):
    """Custom exception raised when a user is not authenticated."""

    pass


def hash_password(password: str) -> str:
    """Hashes a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Generates a signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": int(expire.timestamp())})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def is_token_blacklisted(db: Session, token: str) -> bool:
    """Checks if a token has been blacklisted."""
    return (
        db.query(BlacklistedToken).filter(BlacklistedToken.token == token).first()
        is not None
    )


def blacklist_token(db: Session, token: str, expires_at: datetime) -> None:
    """Saves a token to the blacklist, running cleanup on expired entries first."""
    try:
        # Convert expires_at to naive UTC datetime if it contains timezone info
        if expires_at.tzinfo is not None:
            expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)

        # Expiry cleanup to prevent DB bloating (done here since it's already a write transaction)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.query(BlacklistedToken).filter(BlacklistedToken.expires_at < now).delete()

        blacklisted = BlacklistedToken(token=token, expires_at=expires_at)
        db.add(blacklisted)
        db.commit()
    except Exception:
        db.rollback()


def get_token_expiry(token: str) -> datetime:
    """Decodes a token's exp claim and returns it as a timezone-aware UTC datetime."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        exp = payload.get("exp")
        if exp:
            return datetime.fromtimestamp(exp, tz=timezone.utc)
    except JWTError:
        pass
    # Fallback to standard 1 hour expiration
    return datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)


def get_current_user(request: Request, db: Session = Depends(get_db_session)) -> User:
    """
    FastAPI dependency validating Bearer tokens from either:
    1. Authorization headers (Bearer <token>)
    2. Secure httponly Cookies (access_token)
    """
    token = None
    auth_header = request.headers.get("Authorization")

    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        token = request.cookies.get("access_token")

    if not token:
        raise UnauthenticatedException()

    if is_token_blacklisted(db, token):
        raise UnauthenticatedException()

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise UnauthenticatedException()
    except JWTError:
        raise UnauthenticatedException()

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise UnauthenticatedException()

    # Save user on request state so HTML templates or controllers can retrieve it
    request.state.user = user
    return user


def unauthenticated_exception_handler(request: Request, exc: UnauthenticatedException):
    """
    Handles UnauthenticatedException by:
    - Returning JSON 401 response for API/Streaming paths
    - Redirecting to /login for page requests (HTML)
    """
    accept_header = request.headers.get("accept", "")
    path = request.url.path

    if path.startswith("/api/") or "text/html" not in accept_header:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Not authenticated"},
        )

    from fastapi.responses import RedirectResponse

    # Redirect HTML pages to login path
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
