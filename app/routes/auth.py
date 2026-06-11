import os
import hashlib
import time
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.db import get_db_conn
from app.models.request import UserAuthRequest
from app.utils.logger import get_logger

logger = get_logger("auth-router")
router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "9a4897f26c7e2b7e17df9de7ab365cde78a6eb7f8cf8923a10e8d0e5c9ef3a1b")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))

security = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    """Hashes password securely using standard pure-Python PBKDF2-SHA256."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return f"{salt.hex()}:{key.hex()}"

def verify_password(stored_hash: str, provided_password: str) -> bool:
    """Verifies a password against the stored PBKDF2-SHA256 hash."""
    try:
        salt_hex, key_hex = stored_hash.split(':')
        salt = bytes.fromhex(salt_hex)
        key = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
        return key.hex() == key_hex
    except Exception as e:
        logger.error(f"Password verification failed: {str(e)}")
        return False

def create_access_token(data: dict) -> str:
    """Generates a secure JWT access token."""
    to_encode = data.copy()
    expire = time.time() + (ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def get_current_user_optional(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict | None:
    """
    Dependency that optionally extracts the authenticated user from the JWT token.
    Allows endpoints to act differently for logged-in vs anonymous sessions.
    """
    if not credentials:
        return None
        
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username = payload.get("username")
        user_id = payload.get("id")
        if username is None or user_id is None:
            return None
        return {"id": user_id, "username": username}
    except jwt.PyJWTError:
        return None

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Dependency that strictly enforces JWT authentication, returning user metadata."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization token is missing. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username = payload.get("username")
        user_id = payload.get("id")
        if username is None or user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {"id": user_id, "username": username}
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: UserAuthRequest):
    """Registers a new user inside the SQLite database."""
    username = payload.username.strip()
    password_hash = hash_password(payload.password)
    
    with get_db_conn() as conn:
        cursor = conn.cursor()
        # Check if username exists
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username is already taken."
            )
            
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        conn.commit()
        
    logger.info(f"Successfully registered user: '{username}'")
    return {"message": f"User '{username}' registered successfully."}

@router.post("/login")
def login(payload: UserAuthRequest):
    """Authenticates a user and returns a signed JWT access token."""
    username = payload.username.strip()
    
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        
    if not user or not verify_password(user["password_hash"], payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password."
        )
        
    access_token = create_access_token({"id": user["id"], "username": username})
    
    logger.info(f"User '{username}' logged in successfully.")
    return {
        "accessToken": access_token,
        "tokenType": "bearer",
        "username": username
    }
