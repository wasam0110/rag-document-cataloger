"""
Authentication routes for login with email verification.

Implements a two-step login flow:
  1. POST /auth/register   – create account (email + password).
  2. POST /auth/send-code  – validate password, email a 6-digit code.
  3. POST /auth/verify-login – verify the code and issue a JWT.
Also provides /auth/me (profile) and /auth/logout helpers.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

from app.models.schemas import UserLogin, Token, User
from app.services.auth import authenticate_user, get_current_user
from app.services.email_service import generate_verification_code, get_expiry_time, send_verification_email
from app.db.sqlite import store_verification_code, verify_code
from app.core.logging import logger
from app.core.config import settings

# Create an APIRouter with the /auth prefix; all routes are tagged for OpenAPI grouping.
router = APIRouter(prefix="/auth", tags=["authentication"])


# ──────────────────────────────────────────────
# Request body models (specific to auth routes)
# ──────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """Payload for creating a new user account."""
    email: EmailStr   # Validated email address
    password: str     # Plain-text password (will be hashed server-side)


class SendCodeRequest(BaseModel):
    """Payload for requesting a verification code after password validation."""
    email: EmailStr
    password: str     # Needed to re-verify identity before sending the code


class VerifyCodeRequest(BaseModel):
    """Payload for submitting the 6-digit verification code."""
    email: EmailStr
    code: str         # The 6-digit code the user received via email


# ──────────────────────────────────────────────
# Route handlers
# ──────────────────────────────────────────────

@router.post("/register")
async def register(request: RegisterRequest):
    """Register a new user account.

    Validates that the email is not already taken and that the password
    meets minimum-length requirements, then stores a hashed password.
    """
    try:
        from app.db.sqlite import get_user_by_email, create_user
        from app.services.auth import get_password_hash
        import uuid
        
        logger.info(f"Registration request for: {request.email}")
        
        # Reject if an account with this email already exists
        existing_user = get_user_by_email(request.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered. Please login instead.")
        
        # Enforce a minimum password length for basic security
        if len(request.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
        
        # Generate a unique user ID and hash the password with bcrypt
        user_id = str(uuid.uuid4())
        hashed_password = get_password_hash(request.password)
        
        # Insert the new user record into the database
        success = create_user(
            user_id=user_id,
            email=request.email,
            username=request.email.split('@')[0],  # Default username = email prefix
            hashed_password=hashed_password,
            oauth_provider=None,   # Local registration
            oauth_id=None,
            full_name=None
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to create account")
        
        logger.info(f"User registered successfully: {request.email}")
        return {"message": "Account created successfully. You can now login.", "email": request.email}
        
    except HTTPException:
        raise  # Re-raise known HTTP errors without wrapping
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/send-code")
async def send_code(request: SendCodeRequest):
    """Send a verification code to the user's email after validating the password.

    Flow:
      1. Verify the user exists.
      2. Confirm the supplied password is correct.
      3. Generate a 6-digit code and store it with a 10-minute TTL.
      4. Email the code (or log it in test mode).
    """
    try:
        from app.db.sqlite import get_user_by_email
        
        logger.info(f"Send code request for: {request.email}")
        
        # Ensure the user has a registered account
        user = get_user_by_email(request.email)
        if not user:
            logger.error(f"User not found: {request.email}")
            raise HTTPException(status_code=401, detail="Email not registered. Please sign up first.")
        
        # Re-verify the password before sending a code to prevent abuse
        login_data = UserLogin(email=request.email, password=request.password)
        try:
            logger.info(f"Authenticating user: {request.email}")
            authenticate_user(login_data)  # Raises HTTPException on failure
            logger.info(f"Authentication successful for: {request.email}")
        except HTTPException as e:
            logger.error(f"Authentication failed for {request.email}: {e.detail}")
            raise HTTPException(status_code=401, detail="Incorrect password")
        
        # Generate a random 6-digit verification code
        code = generate_verification_code()
        # Calculate when the code expires (10 minutes from now)
        expires_at = get_expiry_time(minutes=10)
        
        # Persist the code in the DB (invalidates any previously unused codes)
        if not store_verification_code(request.email, code, expires_at):
            raise HTTPException(status_code=500, detail="Failed to store verification code")
        
        # In test mode, skip actual email delivery and return the code in the response
        if settings.email_test_mode:
            logger.info(f"TEST MODE: Verification code for {request.email}: {code}")
            return {
                "message": "TEST MODE: Verification code is 123456 (check console for real code)", 
                "email": request.email,
                "test_code": code  # Included so automated tests can verify without SMTP
            }
        else:
            # Send the code via SMTP
            if not send_verification_email(request.email, code):
                raise HTTPException(status_code=500, detail="Failed to send verification email")
        
        logger.info(f"Verification code sent to {request.email}")
        return {"message": "Verification code sent to your email", "email": request.email}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send code error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-login")
async def verify_and_login(request: VerifyCodeRequest):
    """Verify the emailed code and complete login by issuing a JWT.

    If the code is valid and not expired, the endpoint returns a bearer
    access token that the client stores for subsequent authenticated requests.
    """
    try:
        # Check the code against the database (also marks it as used)
        if not verify_code(request.email, request.code):
            raise HTTPException(status_code=400, detail="Invalid or expired verification code")
        
        # Code is valid – look up the user and create a JWT
        from app.db.sqlite import get_user_by_email, update_user_login
        from app.services.auth import create_access_token
        
        user = get_user_by_email(request.email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Record this login time
        update_user_login(user['user_id'])
        
        # Build the JWT with user_id as "sub" (subject) claim
        token = create_access_token(data={"sub": user['user_id'], "email": user['email']})
        
        logger.info(f"User {request.email} logged in successfully after verification")
        
        # Return token in both JSON body AND set as HttpOnly cookie for reliability
        response = JSONResponse(content={"access_token": token, "token_type": "bearer"})
        response.set_cookie(
            key="auth_token",
            value=token,
            httponly=False,        # Allow JS access so frontend can read it too
            samesite="lax",       # Prevent CSRF while allowing same-site navigation
            path="/",             # Cookie available on all paths
            max_age=60 * 60 * 24 * 7,  # 7 days, same as token expiry
        )
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verify and login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.get("/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the profile of the currently authenticated user.

    The ``get_current_user`` dependency extracts and validates the JWT
    from the Authorization header automatically.
    """
    return current_user


@router.post("/logout")
async def logout():
    """Logout endpoint.

    Clears the auth_token cookie. The client is also responsible
    for deleting the token stored in localStorage.
    """
    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie(key="auth_token", path="/")
    return response
