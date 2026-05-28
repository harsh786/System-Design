# Redis Sessions & Authentication Patterns

## Why Redis for Sessions

HTTP is stateless. Sessions bridge the gap — they let the server remember who a user is across requests. Redis is the de facto session store because:

1. **Sub-millisecond reads** — session lookup on every request must be fast
2. **Built-in TTL** — sessions expire naturally without cleanup jobs
3. **Atomic operations** — concurrent requests from the same user don't corrupt session data
4. **Shared state** — all app server instances see the same sessions (horizontal scaling)
5. **Memory-efficient** — a typical session (1-2KB) × 1M users = ~2GB

---

## Pattern 1: Basic Session Store

### Session Lifecycle

```
[Client]                    [App Server]                    [Redis]
   |-- POST /login ------------>|                              |
   |                            |-- HSET session:{id} ... ---->|
   |                            |-- EXPIRE session:{id} 3600 ->|
   |<-- Set-Cookie: sid={id} ---|                              |
   |                            |                              |
   |-- GET /dashboard --------->|                              |
   |   Cookie: sid={id}         |-- HGETALL session:{id} ----->|
   |                            |<-- {user_id, role, ...} -----|
   |<-- 200 OK + data ---------|                              |
   |                            |                              |
   |-- POST /logout ----------->|                              |
   |                            |-- DEL session:{id} --------->|
   |<-- Set-Cookie: sid=; exp=0-|                              |
```

### Implementation

```python
import redis
import uuid
import hashlib
import time
import json
from typing import Optional

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

SESSION_TTL = 3600  # 1 hour
SESSION_PREFIX = "session:"


def generate_session_id() -> str:
    """
    Generate a cryptographically random session ID.
    
    Requirements:
    - Unguessable (128+ bits of entropy)
    - URL-safe (no special chars that need encoding)
    - Fixed length (for consistent key sizes)
    """
    return uuid.uuid4().hex + uuid.uuid4().hex  # 256 bits / 64 hex chars


def create_session(user_id: str, metadata: dict = None) -> str:
    """
    Create a new session after successful authentication.
    
    Stores session as a Redis Hash — efficient for partial reads/writes
    compared to serialized JSON in a String.
    """
    session_id = generate_session_id()
    key = f"{SESSION_PREFIX}{session_id}"
    
    session_data = {
        "user_id": user_id,
        "created_at": str(int(time.time())),
        "last_active": str(int(time.time())),
        "ip": metadata.get("ip", "") if metadata else "",
        "user_agent": metadata.get("user_agent", "") if metadata else "",
    }
    
    if metadata:
        for k, v in metadata.items():
            if k not in session_data:
                session_data[k] = str(v)
    
    pipe = r.pipeline()
    pipe.hset(key, mapping=session_data)
    pipe.expire(key, SESSION_TTL)
    pipe.execute()
    
    return session_id


def get_session(session_id: str) -> Optional[dict]:
    """
    Retrieve and validate a session.
    Returns None if session doesn't exist or is expired.
    """
    key = f"{SESSION_PREFIX}{session_id}"
    session_data = r.hgetall(key)
    
    if not session_data:
        return None
    
    return session_data


def touch_session(session_id: str) -> bool:
    """
    Extend session TTL on activity (sliding expiration).
    
    Trade-off: Sliding expiration keeps active users logged in but
    means a session could theoretically live forever with constant activity.
    Mitigate with absolute maximum lifetime (see Pattern 3).
    """
    key = f"{SESSION_PREFIX}{session_id}"
    
    pipe = r.pipeline()
    pipe.hset(key, "last_active", str(int(time.time())))
    pipe.expire(key, SESSION_TTL)
    results = pipe.execute()
    
    return results[0] is not None


def destroy_session(session_id: str):
    """Delete session on logout."""
    r.delete(f"{SESSION_PREFIX}{session_id}")


def update_session(session_id: str, updates: dict) -> bool:
    """Update specific session fields without overwriting others."""
    key = f"{SESSION_PREFIX}{session_id}"
    
    if not r.exists(key):
        return False
    
    updates["last_active"] = str(int(time.time()))
    r.hset(key, mapping=updates)
    return True
```

---

## Pattern 2: Session with CSRF Protection

```python
import redis
import secrets
import hmac
import hashlib

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

def create_session_with_csrf(user_id: str, metadata: dict = None) -> dict:
    """
    Create session with bound CSRF token.
    
    The CSRF token is stored IN the session and must be presented
    by the client in a custom header (X-CSRF-Token) on state-changing requests.
    
    Why not just use the session cookie as CSRF protection?
    - Cookies are sent automatically by the browser on every request
    - A malicious site can trigger requests that include the victim's cookies
    - CSRF tokens require explicit JavaScript access, which same-origin policy blocks
    """
    session_id = generate_session_id()
    csrf_token = secrets.token_hex(32)
    
    key = f"session:{session_id}"
    session_data = {
        "user_id": user_id,
        "csrf_token": csrf_token,
        "created_at": str(int(time.time())),
        "last_active": str(int(time.time())),
    }
    
    if metadata:
        session_data.update({k: str(v) for k, v in metadata.items()})
    
    pipe = r.pipeline()
    pipe.hset(key, mapping=session_data)
    pipe.expire(key, 3600)
    pipe.execute()
    
    return {
        "session_id": session_id,
        "csrf_token": csrf_token,
    }


def validate_csrf(session_id: str, presented_csrf: str) -> bool:
    """
    Validate CSRF token matches what's stored in the session.
    Uses constant-time comparison to prevent timing attacks.
    """
    stored_csrf = r.hget(f"session:{session_id}", "csrf_token")
    if not stored_csrf:
        return False
    return hmac.compare_digest(stored_csrf, presented_csrf)
```

---

## Pattern 3: Absolute + Sliding Expiration

```python
import redis
import time

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

SESSION_IDLE_TTL = 1800       # 30 minutes of inactivity → expire
SESSION_ABSOLUTE_TTL = 86400  # 24 hours max lifetime regardless of activity


def create_session_dual_expiry(user_id: str) -> str:
    """
    Session with both idle timeout and absolute maximum lifetime.
    
    - Idle timeout: resets on every request (sliding)
    - Absolute timeout: never extends, forces re-authentication
    
    This prevents the "infinite session" problem where sliding expiration
    keeps a session alive indefinitely for an active user.
    """
    session_id = generate_session_id()
    now = int(time.time())
    absolute_expiry = now + SESSION_ABSOLUTE_TTL
    
    key = f"session:{session_id}"
    session_data = {
        "user_id": user_id,
        "created_at": str(now),
        "last_active": str(now),
        "absolute_expiry": str(absolute_expiry),
    }
    
    pipe = r.pipeline()
    pipe.hset(key, mapping=session_data)
    pipe.expire(key, SESSION_IDLE_TTL)
    pipe.execute()
    
    return session_id


TOUCH_WITH_ABSOLUTE_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local idle_ttl = tonumber(ARGV[2])

local absolute_expiry = tonumber(redis.call('HGET', key, 'absolute_expiry') or '0')

if absolute_expiry == 0 then
    return {0, 0}  -- session doesn't exist
end

if now >= absolute_expiry then
    redis.call('DEL', key)
    return {0, 1}  -- session expired (absolute)
end

-- Calculate remaining absolute time
local remaining = absolute_expiry - now
-- Use the shorter of idle_ttl and remaining absolute time
local new_ttl = math.min(idle_ttl, remaining)

redis.call('HSET', key, 'last_active', tostring(now))
redis.call('EXPIRE', key, new_ttl)

return {1, new_ttl}
"""

def touch_session_with_absolute(session_id: str) -> dict:
    """Extend session but respect absolute maximum lifetime."""
    key = f"session:{session_id}"
    now = int(time.time())
    
    result = r.execute_command(
        "EVAL", TOUCH_WITH_ABSOLUTE_LUA, 1, key,
        str(now), str(SESSION_IDLE_TTL)
    )
    
    if result[0] == 0:
        reason = "not_found" if result[1] == 0 else "absolute_expired"
        return {"valid": False, "reason": reason}
    
    return {"valid": True, "ttl_remaining": result[1]}
```

---

## Pattern 4: Multi-Device Session Management

```python
import redis
import time

r = redis.Redis(host='localhost', port=6379, decode_responses=True)


class MultiDeviceSessionManager:
    """
    Manages multiple concurrent sessions per user across devices.
    
    Architecture:
    - session:{session_id} → Hash (session data)
    - user_sessions:{user_id} → Set of active session IDs
    
    This enables:
    - "Sign out all devices"
    - "View active sessions" (settings page)
    - Limit concurrent sessions (e.g., max 5)
    - Invalidate specific device sessions
    """
    
    MAX_SESSIONS_PER_USER = 10
    
    def __init__(self, redis_client):
        self.r = redis_client
    
    def create_session(self, user_id: str, device_info: dict) -> str:
        session_id = generate_session_id()
        now = int(time.time())
        
        key = f"session:{session_id}"
        user_sessions_key = f"user_sessions:{user_id}"
        
        session_data = {
            "user_id": user_id,
            "session_id": session_id,
            "created_at": str(now),
            "last_active": str(now),
            "device_type": device_info.get("type", "unknown"),
            "device_name": device_info.get("name", "unknown"),
            "ip": device_info.get("ip", ""),
            "location": device_info.get("location", ""),
        }
        
        pipe = self.r.pipeline()
        pipe.hset(key, mapping=session_data)
        pipe.expire(key, 86400)
        pipe.sadd(user_sessions_key, session_id)
        pipe.expire(user_sessions_key, 86400 * 30)  # Keep user session index for 30 days
        pipe.execute()
        
        # Enforce max sessions (remove oldest if exceeded)
        self._enforce_session_limit(user_id)
        
        return session_id
    
    def get_all_user_sessions(self, user_id: str) -> list:
        """Get all active sessions for a user (for "active sessions" settings page)."""
        user_sessions_key = f"user_sessions:{user_id}"
        session_ids = self.r.smembers(user_sessions_key)
        
        if not session_ids:
            return []
        
        sessions = []
        pipe = self.r.pipeline()
        for sid in session_ids:
            pipe.hgetall(f"session:{sid}")
        results = pipe.execute()
        
        valid_sessions = []
        expired_ids = []
        
        for sid, data in zip(session_ids, results):
            if data:
                valid_sessions.append(data)
            else:
                expired_ids.append(sid)
        
        # Clean up expired session references
        if expired_ids:
            self.r.srem(user_sessions_key, *expired_ids)
        
        return valid_sessions
    
    def revoke_session(self, user_id: str, session_id: str):
        """Revoke a specific session (e.g., user clicks 'sign out' on a device)."""
        pipe = self.r.pipeline()
        pipe.delete(f"session:{session_id}")
        pipe.srem(f"user_sessions:{user_id}", session_id)
        pipe.execute()
    
    def revoke_all_sessions(self, user_id: str, except_session_id: str = None):
        """
        Sign out all devices. Optionally keep the current session.
        Used after password change or security incident.
        """
        user_sessions_key = f"user_sessions:{user_id}"
        session_ids = self.r.smembers(user_sessions_key)
        
        if not session_ids:
            return
        
        pipe = self.r.pipeline()
        for sid in session_ids:
            if sid != except_session_id:
                pipe.delete(f"session:{sid}")
                pipe.srem(user_sessions_key, sid)
        pipe.execute()
    
    def _enforce_session_limit(self, user_id: str):
        """Remove oldest sessions if user exceeds max concurrent sessions."""
        sessions = self.get_all_user_sessions(user_id)
        
        if len(sessions) <= self.MAX_SESSIONS_PER_USER:
            return
        
        # Sort by created_at, remove oldest
        sessions.sort(key=lambda s: int(s.get("created_at", "0")))
        to_remove = sessions[:len(sessions) - self.MAX_SESSIONS_PER_USER]
        
        pipe = self.r.pipeline()
        for session in to_remove:
            sid = session["session_id"]
            pipe.delete(f"session:{sid}")
            pipe.srem(f"user_sessions:{user_id}", sid)
        pipe.execute()
```

---

## Pattern 5: Token Blacklist (JWT Revocation)

JWTs are stateless — you can't "invalidate" them without server-side state. Redis is the standard solution:

```python
import redis
import time
import jwt

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

JWT_SECRET = "your-secret-key"  # In production: from secrets manager


class TokenBlacklist:
    """
    Maintains a blacklist of revoked JWT tokens.
    
    Architecture choices:
    
    Option A: Blacklist (what we implement here)
    - Store revoked token JTI (JWT ID) in Redis
    - TTL = remaining token lifetime (auto-cleanup)
    - Check blacklist on every request
    - Pros: Works with existing JWTs, minimal storage
    - Cons: Extra Redis lookup per request
    
    Option B: Allowlist (not shown)
    - Store ALL valid tokens in Redis
    - Delete from Redis to revoke
    - Pros: Simpler revocation model
    - Cons: Loses the stateless benefit of JWTs entirely
    
    Option C: Short-lived tokens + refresh (recommended for new systems)
    - Access token: 15 minutes, no Redis check needed
    - Refresh token: 7 days, stored in Redis
    - Revoke by deleting refresh token
    - Pros: Best balance of performance and security
    """
    
    PREFIX = "token:blacklist:"
    
    def __init__(self, redis_client):
        self.r = redis_client
    
    def revoke_token(self, token: str):
        """
        Add token to blacklist with TTL matching its remaining lifetime.
        After the token's natural expiry, the blacklist entry is automatically removed.
        """
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"],
                               options={"verify_exp": False})
        except jwt.InvalidTokenError:
            return  # Invalid token, nothing to blacklist
        
        jti = payload.get("jti")
        exp = payload.get("exp")
        
        if not jti or not exp:
            return
        
        remaining_ttl = exp - int(time.time())
        if remaining_ttl <= 0:
            return  # Already expired, no need to blacklist
        
        self.r.setex(f"{self.PREFIX}{jti}", remaining_ttl, "revoked")
    
    def is_revoked(self, token: str) -> bool:
        """Check if a token has been revoked. Called on every authenticated request."""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"],
                               options={"verify_exp": False})
        except jwt.InvalidTokenError:
            return True  # Can't decode = treat as revoked
        
        jti = payload.get("jti")
        if not jti:
            return False  # No JTI = can't be blacklisted
        
        return self.r.exists(f"{self.PREFIX}{jti}") == 1
    
    def revoke_all_user_tokens(self, user_id: str, issued_before: int = None):
        """
        Revoke all tokens for a user by storing a "revoked_before" timestamp.
        Any token issued before this timestamp is considered invalid.
        
        More efficient than blacklisting individual tokens when doing
        "sign out everywhere" — stores one key instead of N.
        """
        timestamp = issued_before or int(time.time())
        # Store for the maximum possible token lifetime
        self.r.setex(f"user:revoked_before:{user_id}", 86400 * 7, str(timestamp))
    
    def is_user_token_revoked(self, user_id: str, issued_at: int) -> bool:
        """Check if a user's token was issued before the revocation timestamp."""
        revoked_before = self.r.get(f"user:revoked_before:{user_id}")
        if not revoked_before:
            return False
        return issued_at < int(revoked_before)
```

---

## Pattern 6: Refresh Token Rotation

```python
import redis
import secrets
import time
import json

r = redis.Redis(host='localhost', port=6379, decode_responses=True)


class RefreshTokenStore:
    """
    Secure refresh token management with rotation.
    
    Flow:
    1. Login → Issue access token (15min) + refresh token (7 days)
    2. Access token expires → Client sends refresh token
    3. Server validates refresh token → Issues NEW access token + NEW refresh token
    4. Old refresh token is immediately invalidated
    
    Why rotation matters:
    - If a refresh token is stolen, it can only be used once
    - When the legitimate user tries to refresh with the old token,
      it fails → signals token theft → revoke entire family
    
    Token Family:
    - All refresh tokens descending from one login form a "family"
    - If any old token in the family is reused, the entire family is revoked
    - This detects token theft even if the attacker uses it first
    """
    
    REFRESH_TTL = 86400 * 7  # 7 days
    
    def __init__(self, redis_client):
        self.r = redis_client
    
    def create_refresh_token(self, user_id: str, device_id: str, family_id: str = None) -> dict:
        """Create a new refresh token, optionally as part of an existing family."""
        token = secrets.token_urlsafe(48)
        family_id = family_id or secrets.token_urlsafe(16)
        now = int(time.time())
        
        token_data = {
            "user_id": user_id,
            "device_id": device_id,
            "family_id": family_id,
            "created_at": str(now),
            "used": "false",
        }
        
        pipe = self.r.pipeline()
        # Store token data
        pipe.hset(f"refresh_token:{token}", mapping=token_data)
        pipe.expire(f"refresh_token:{token}", self.REFRESH_TTL)
        
        # Add to user's token set (for "view active sessions")
        pipe.sadd(f"user_refresh_tokens:{user_id}", token)
        pipe.expire(f"user_refresh_tokens:{user_id}", self.REFRESH_TTL)
        
        # Track token family
        pipe.sadd(f"token_family:{family_id}", token)
        pipe.expire(f"token_family:{family_id}", self.REFRESH_TTL)
        
        pipe.execute()
        
        return {
            "refresh_token": token,
            "family_id": family_id,
            "expires_at": now + self.REFRESH_TTL,
        }
    
    def rotate_refresh_token(self, old_token: str) -> dict:
        """
        Validate old token, mark it used, issue new token in same family.
        
        Returns new tokens if valid, None if invalid/stolen.
        """
        key = f"refresh_token:{old_token}"
        token_data = self.r.hgetall(key)
        
        if not token_data:
            return {"error": "token_not_found"}
        
        # Check if token was already used (replay attack / theft detection)
        if token_data.get("used") == "true":
            # TOKEN THEFT DETECTED — revoke entire family
            family_id = token_data["family_id"]
            self._revoke_family(family_id, token_data["user_id"])
            return {"error": "token_reuse_detected", "action": "family_revoked"}
        
        # Mark old token as used (but don't delete — need for theft detection)
        self.r.hset(key, "used", "true")
        self.r.expire(key, 86400)  # Keep for 24h for theft detection
        
        # Issue new token in same family
        new_token = self.create_refresh_token(
            user_id=token_data["user_id"],
            device_id=token_data["device_id"],
            family_id=token_data["family_id"],
        )
        
        return {"success": True, **new_token}
    
    def _revoke_family(self, family_id: str, user_id: str):
        """Revoke all tokens in a family (theft response)."""
        family_key = f"token_family:{family_id}"
        tokens = self.r.smembers(family_key)
        
        if tokens:
            pipe = self.r.pipeline()
            for token in tokens:
                pipe.delete(f"refresh_token:{token}")
                pipe.srem(f"user_refresh_tokens:{user_id}", token)
            pipe.delete(family_key)
            pipe.execute()
    
    def revoke_all_user_tokens(self, user_id: str):
        """Revoke all refresh tokens for a user (password change, security event)."""
        tokens = self.r.smembers(f"user_refresh_tokens:{user_id}")
        
        if tokens:
            pipe = self.r.pipeline()
            for token in tokens:
                # Get family_id before deleting
                family_id = self.r.hget(f"refresh_token:{token}", "family_id")
                pipe.delete(f"refresh_token:{token}")
                if family_id:
                    pipe.delete(f"token_family:{family_id}")
            pipe.delete(f"user_refresh_tokens:{user_id}")
            pipe.execute()
```

---

## Pattern 7: Login Attempt Rate Limiting

```python
import redis
import time

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

LOGIN_RATE_LIMIT_LUA = """
local key = KEYS[1]
local lockout_key = KEYS[2]
local max_attempts = tonumber(ARGV[1])
local window_seconds = tonumber(ARGV[2])
local lockout_seconds = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

-- Check if already locked out
if redis.call('EXISTS', lockout_key) == 1 then
    local ttl = redis.call('TTL', lockout_key)
    return {0, 0, ttl}  -- locked out, 0 remaining, seconds until unlock
end

-- Remove old attempts
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window_seconds)

-- Count recent attempts
local attempts = redis.call('ZCARD', key)

if attempts >= max_attempts then
    -- Trigger lockout
    redis.call('SET', lockout_key, '1')
    redis.call('EXPIRE', lockout_key, lockout_seconds)
    redis.call('DEL', key)
    return {0, 0, lockout_seconds}
end

-- Record this attempt
redis.call('ZADD', key, now, now .. ':' .. math.random(1000000))
redis.call('EXPIRE', key, window_seconds)

local remaining = max_attempts - attempts - 1
return {1, remaining, 0}
"""


class LoginRateLimiter:
    """
    Progressive rate limiting for login attempts.
    
    Policy:
    - 5 failed attempts in 15 minutes → lock for 15 minutes
    - 10 failed attempts in 1 hour → lock for 1 hour
    - 20 failed attempts in 24 hours → lock for 24 hours + alert security team
    
    Rate limit by BOTH:
    - Username/email (prevents credential stuffing against one account)
    - IP address (prevents distributed attacks from one source)
    """
    
    POLICIES = [
        {"max_attempts": 5, "window": 900, "lockout": 900},      # 5 in 15min → 15min lock
        {"max_attempts": 10, "window": 3600, "lockout": 3600},   # 10 in 1hr → 1hr lock
        {"max_attempts": 20, "window": 86400, "lockout": 86400}, # 20 in 24hr → 24hr lock
    ]
    
    def __init__(self, redis_client):
        self.r = redis_client
    
    def check_login_allowed(self, identifier: str, identifier_type: str = "email") -> dict:
        """
        Check if a login attempt is allowed.
        Call BEFORE validating credentials.
        """
        for i, policy in enumerate(self.POLICIES):
            key = f"login_attempts:{identifier_type}:{identifier}:tier{i}"
            lockout_key = f"login_lockout:{identifier_type}:{identifier}:tier{i}"
            now = time.time()
            
            result = self.r.execute_command(
                "EVAL", LOGIN_RATE_LIMIT_LUA, 2, key, lockout_key,
                str(policy["max_attempts"]), str(policy["window"]),
                str(policy["lockout"]), str(now)
            )
            
            if result[0] == 0:
                return {
                    "allowed": False,
                    "reason": "too_many_attempts",
                    "retry_after_seconds": result[2],
                    "tier": i,
                }
        
        return {"allowed": True, "attempts_remaining": result[1]}
    
    def record_failed_attempt(self, email: str, ip: str):
        """Record a failed login attempt against both email and IP."""
        now = time.time()
        pipe = self.r.pipeline()
        
        for identifier, id_type in [(email, "email"), (ip, "ip")]:
            for i, policy in enumerate(self.POLICIES):
                key = f"login_attempts:{id_type}:{identifier}:tier{i}"
                pipe.zadd(key, {f"{now}:{id_type}": now})
                pipe.expire(key, policy["window"])
        
        pipe.execute()
    
    def clear_attempts(self, email: str):
        """Clear attempts after successful login."""
        pipe = self.r.pipeline()
        for i in range(len(self.POLICIES)):
            pipe.delete(f"login_attempts:email:{email}:tier{i}")
            pipe.delete(f"login_lockout:email:{email}:tier{i}")
        pipe.execute()
```

---

## Pattern 8: OAuth State Parameter Store

```python
import redis
import secrets
import json
import time

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

OAUTH_STATE_TTL = 600  # 10 minutes — OAuth flow should complete within this time


def create_oauth_state(provider: str, redirect_uri: str, extra_data: dict = None) -> str:
    """
    Generate and store OAuth state parameter.
    
    The state parameter prevents CSRF in OAuth flows:
    1. Generate random state, store in Redis
    2. Send state with OAuth authorization URL
    3. Provider redirects back with same state
    4. Verify state exists in Redis (proves the flow was initiated by us)
    5. Delete state (one-time use)
    
    Also stores metadata needed to complete the flow (redirect_uri, etc.)
    """
    state = secrets.token_urlsafe(32)
    
    state_data = {
        "provider": provider,
        "redirect_uri": redirect_uri,
        "created_at": str(int(time.time())),
    }
    
    if extra_data:
        state_data.update({k: str(v) for k, v in extra_data.items()})
    
    r.setex(
        f"oauth_state:{state}",
        OAUTH_STATE_TTL,
        json.dumps(state_data)
    )
    
    return state


def validate_oauth_state(state: str) -> dict:
    """
    Validate and consume OAuth state (one-time use).
    Returns stored data if valid, None if invalid/expired/reused.
    """
    key = f"oauth_state:{state}"
    
    # GET and DELETE atomically to prevent race conditions
    pipe = r.pipeline()
    pipe.get(key)
    pipe.delete(key)
    results = pipe.execute()
    
    data = results[0]
    if not data:
        return None
    
    return json.loads(data)
```

---

## Pattern 9: Permission Cache

```python
import redis
import json
import time

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

PERMISSION_CACHE_TTL = 300  # 5 minutes


class PermissionCache:
    """
    Caches user permissions/roles to avoid database lookups on every request.
    
    Pattern: Cache-aside with event-driven invalidation.
    
    Read path:
    1. Check Redis for cached permissions
    2. If miss → query database → write to Redis
    3. Return permissions
    
    Write path (permission change):
    1. Update database
    2. Delete Redis cache key (invalidate)
    3. Next read will repopulate from database
    
    Why not update cache on write?
    - Invalidation is simpler and avoids race conditions
    - Database is source of truth
    - Stale reads are bounded by TTL
    """
    
    def __init__(self, redis_client):
        self.r = redis_client
    
    def get_permissions(self, user_id: str) -> dict:
        """Get cached permissions. Returns None on cache miss."""
        data = self.r.get(f"permissions:{user_id}")
        if data:
            return json.loads(data)
        return None
    
    def set_permissions(self, user_id: str, permissions: dict):
        """Cache permissions after database lookup."""
        self.r.setex(
            f"permissions:{user_id}",
            PERMISSION_CACHE_TTL,
            json.dumps(permissions)
        )
    
    def invalidate_permissions(self, user_id: str):
        """Invalidate cache when permissions change."""
        self.r.delete(f"permissions:{user_id}")
    
    def invalidate_role_members(self, role: str, member_ids: list):
        """
        Invalidate all users with a given role (bulk invalidation).
        Called when a role's permissions are changed.
        """
        if not member_ids:
            return
        
        keys = [f"permissions:{uid}" for uid in member_ids]
        self.r.delete(*keys)
    
    def check_permission(self, user_id: str, resource: str, action: str) -> bool:
        """Check a specific permission (after loading from cache/db)."""
        permissions = self.get_permissions(user_id)
        if permissions is None:
            return None  # Cache miss — caller must fetch from DB
        
        # Check direct permissions
        resource_perms = permissions.get("resources", {}).get(resource, [])
        if action in resource_perms or "*" in resource_perms:
            return True
        
        # Check role-based permissions
        roles = permissions.get("roles", [])
        if "admin" in roles:
            return True
        
        return False
```

---

## Production Best Practices

### Session Security Checklist

| Concern | Mitigation |
|---------|-----------|
| Session fixation | Generate new session ID after login |
| Session hijacking | Bind session to IP + User-Agent fingerprint |
| XSS token theft | HttpOnly + Secure + SameSite=Strict cookies |
| CSRF | Bound CSRF token verified on state-changing requests |
| Brute force session IDs | Use 256-bit random IDs (uuid4 × 2) |
| Indefinite sessions | Absolute maximum lifetime (24h) |
| Stale permissions | Short permission cache TTL + event invalidation |
| Token theft (JWT) | Refresh token rotation + family revocation |

### Redis Configuration for Sessions

```
# redis.conf optimized for session workload

# Sessions are small but numerous — optimize for many keys
maxmemory 4gb
maxmemory-policy volatile-lru  # Evict expired keys first, then LRU

# Persistence: sessions are regenerable, so RDB snapshots are sufficient
save 300 100  # Snapshot every 5 min if 100+ keys changed
# Disable AOF for session stores (regenerable data)
appendonly no

# Connection limits for session-heavy workloads
maxclients 10000
timeout 300  # Close idle connections after 5 minutes
tcp-keepalive 60
```

### Key Naming Conventions

```
session:{session_id}              → Hash (session data)
user_sessions:{user_id}           → Set (session IDs for this user)
refresh_token:{token}             → Hash (refresh token data)
user_refresh_tokens:{user_id}     → Set (refresh tokens for user)
token:blacklist:{jti}             → String (revoked JWT marker)
user:revoked_before:{user_id}     → String (timestamp)
oauth_state:{state}               → String (JSON state data)
permissions:{user_id}             → String (JSON permissions)
login_attempts:{type}:{id}:tier{n} → Sorted Set (timestamps)
login_lockout:{type}:{id}:tier{n}  → String (lockout marker)
```

### Session Store Sizing

```
Typical session size: 500 bytes (Hash with 8-10 fields)
Per-user overhead: ~600 bytes (session + index entries)

Example:
- 1M concurrent sessions × 600 bytes = ~600MB
- 10M concurrent sessions × 600 bytes = ~6GB
- Plus Redis overhead (~30%): multiply by 1.3

Rule of thumb: Plan for 1KB per concurrent session including overhead.
```
