"""
Authentication module.
JWT token validation, user extraction, role-based access.
"""

import time
from jose import jwt, JWTError
from config import JWT_SECRET

ALGORITHM = "HS256"

# Roles and their permissions
ROLES = {
    "admin": ["query", "admin", "cost_report"],
    "user": ["query"],
    "readonly": ["query"],
}


def generate_token(user_id: str, role: str = "user", expires_in: int = 3600) -> str:
    """Generate a JWT token for testing."""
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_in,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)
    print(f"[AUTH] Generated token for user={user_id} role={role}")
    return token


def validate_token(token: str) -> dict:
    """
    Validate JWT token and return user context.
    Returns: {"user_id": str, "role": str} or raises exception.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_context = {
            "user_id": payload["sub"],
            "role": payload.get("role", "user"),
        }
        print(f"[AUTH] Validated token: user={user_context['user_id']} role={user_context['role']}")
        return user_context
    except JWTError as e:
        print(f"[AUTH] Token validation FAILED: {e}")
        raise ValueError(f"Invalid token: {e}")


def check_permission(user_context: dict, action: str) -> bool:
    """Check if user has permission for action."""
    role = user_context.get("role", "user")
    permissions = ROLES.get(role, [])
    allowed = action in permissions
    if not allowed:
        print(f"[AUTH] Permission DENIED: user={user_context['user_id']} action={action} role={role}")
    return allowed
