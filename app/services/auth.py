"""
Authentication service for user management, JWT tokens, and OAuth.

Provides password hashing (bcrypt), JWT creation / decoding, and
high-level register / authenticate workflows.  The ``get_current_user``
dependency is injected into protected FastAPI routes via ``Depends()``.
"""

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt                              # JWT encode / decode (python-jose)
from passlib.context import CryptContext                    # Password hashing abstraction
from fastapi import HTTPException, status, Request
from fastapi.security import HTTPBearer

# Database helpers for user CRUD operations
from app.db.sqlite import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    update_user_login
)
from app.models.schemas import User, UserCreate, UserLogin, Token, TokenData
from app.core.logging import logger

# ──────────────────────────────────────────────
# JWT Configuration
# ──────────────────────────────────────────────
# Secret used to sign tokens – should be overridden via the SECRET_KEY env var
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production-please")
ALGORITHM = "HS256"                        # HMAC-SHA256 signing algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # Tokens are valid for 7 days

# ──────────────────────────────────────────────
# Password Hashing
# ──────────────────────────────────────────────
# CryptContext handles hashing and verification; bcrypt is the only scheme.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ──────────────────────────────────────────────
# FastAPI Security Scheme
# ──────────────────────────────────────────────
# HTTPBearer is kept for OpenAPI docs but NOT used as the sole dependency.
# Instead, get_current_user manually extracts the token from header OR cookie.
security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compare a plain-text password against its bcrypt hash.

    Truncates to 72 bytes because bcrypt silently ignores bytes beyond that.
    """
    return pwd_context.verify(plain_password[:72], hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt.

    Truncated to 72 bytes to match the bcrypt maximum input length.
    """
    return pwd_context.hash(password[:72])


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token.

    Args:
        data: Claims to embed (typically {"sub": user_id, "email": …}).
        expires_delta: Custom lifetime; defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()  # Avoid mutating the caller's dict
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})  # Add the expiration claim
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> TokenData:
    """Decode and verify a JWT token, returning the embedded claims.

    Raises:
        HTTPException 401 if the token is invalid, expired, or missing required claims.
    """
    try:
        # Decode the token and verify its signature + expiration
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")    # "sub" holds the user ID
        email: str = payload.get("email")    # Custom claim for convenience
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        return TokenData(user_id=user_id, email=email)
    except JWTError:
        # Catches signature failures, expiry, malformed tokens, etc.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )


def _extract_token(request: Request) -> str:
    """Extract JWT token from Authorization header or auth_token cookie.

    Checks in order:
      1. Authorization: Bearer <token> header
      2. auth_token cookie (set at login)

    Returns the raw token string.
    Raises HTTPException 401 if no valid token source is found.
    """
    # 1. Try Authorization header
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1]:
            logger.debug(f"Token from Authorization header (first 20 chars): {parts[1][:20]}...")
            return parts[1]

    # 2. Try auth_token cookie
    cookie_token = request.cookies.get("auth_token")
    if cookie_token:
        logger.debug(f"Token from cookie (first 20 chars): {cookie_token[:20]}...")
        return cookie_token

    # No token found anywhere
    logger.warning("No authentication token found in header or cookie")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(request: Request) -> User:
    """FastAPI dependency that extracts and validates the current user from the JWT.

    Extracts the token from the Authorization header or auth_token cookie,
    decodes it, and looks up the user in the database.

    Usage in a route:  ``current_user: User = Depends(get_current_user)``
    """
    token = _extract_token(request)          # Get token from header or cookie
    token_data = decode_token(token)         # Validate and extract claims
    
    # Look the user up in the database by the ID stored in the token
    user_dict = get_user_by_id(token_data.user_id)
    if user_dict is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Convert the raw database dict into a typed Pydantic User model
    user = User(
        user_id=user_dict["user_id"],
        email=user_dict["email"],
        username=user_dict.get("username"),
        full_name=user_dict.get("full_name"),
        is_active=bool(user_dict["is_active"]),
        oauth_provider=user_dict.get("oauth_provider"),
        created_at=datetime.fromisoformat(user_dict["created_at"])
    )
    
    return user


def register_user(user_data: UserCreate) -> Token:
    """Register a new user with email and password.

    Steps:
      1. Check for duplicate email.
      2. Hash the password and create the DB record.
      3. Update last-login timestamp.
      4. Issue a JWT access token.

    Returns:
        Token containing the JWT and user details.
    """
    # Prevent duplicate registrations
    existing_user = get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Generate a unique user ID and hash the plain-text password
    user_id = str(uuid.uuid4())
    hashed_password = get_password_hash(user_data.password)
    
    # Persist the user record in SQLite
    success = create_user(
        user_id=user_id,
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        oauth_provider=None,      # Local registration – no OAuth
        oauth_id=None,
        full_name=user_data.full_name
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )
    
    # Record the login timestamp for the brand-new user
    update_user_login(user_id)
    
    # Issue a JWT with the user's ID and email as claims
    access_token = create_access_token(
        data={"sub": user_id, "email": user_data.email}
    )
    
    # Re-fetch user from DB to build the response model
    user_dict = get_user_by_id(user_id)
    user = User(
        user_id=user_dict["user_id"],
        email=user_dict["email"],
        username=user_dict.get("username"),
        full_name=user_dict.get("full_name"),
        is_active=bool(user_dict["is_active"]),
        oauth_provider=user_dict.get("oauth_provider"),
        created_at=datetime.utcnow()
    )
    
    return Token(access_token=access_token, user=user)


def authenticate_user(login_data: UserLogin) -> Token:
    """Authenticate a user with email and password.

    Steps:
      1. Look up the user by email.
      2. Verify the password against the stored hash.
      3. Update last-login timestamp.
      4. Issue a JWT access token.

    Raises:
        HTTPException 401 for unknown emails, missing passwords, or mismatches.
    """
    user_dict = get_user_by_email(login_data.email)
    
    if not user_dict:
        # No account with this email exists
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not user_dict.get("hashed_password"):
        # User signed up via OAuth and has no local password
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please login using OAuth provider"
        )
    
    if not verify_password(login_data.password, user_dict["hashed_password"]):
        # Password does not match the stored hash
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Successful authentication – update last-login time
    update_user_login(user_dict["user_id"])
    
    # Issue a JWT access token
    access_token = create_access_token(
        data={"sub": user_dict["user_id"], "email": user_dict["email"]}
    )
    
    # Build User model for the response
    user = User(
        user_id=user_dict["user_id"],
        email=user_dict["email"],
        username=user_dict.get("username"),
        full_name=user_dict.get("full_name"),
        is_active=bool(user_dict["is_active"]),
        oauth_provider=user_dict.get("oauth_provider"),
        created_at=datetime.fromisoformat(user_dict["created_at"])
    )
    
    return Token(access_token=access_token, user=user)
