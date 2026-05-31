# Redis Shopping Cart & Feature Flags — Deep Dive

## Part 1: Shopping Cart with Redis

### Why Redis for Shopping Carts?

Shopping carts are ephemeral, high-frequency, session-bound data structures. They need:
- Sub-millisecond reads (every page load shows cart count)
- Atomic updates (concurrent tabs adding items)
- TTL support (abandoned cart expiration)
- No need for ACID transactions or complex joins

Redis Hashes are the perfect fit — each cart is a Hash where fields are product IDs and values are JSON-encoded item metadata.

---

### Data Model Design

```
Key Pattern: cart:{user_id}
Type: Hash
Fields: product_id → JSON({quantity, price, name, variant, added_at})

Key Pattern: cart:anon:{session_id}
Type: Hash (same structure, for unauthenticated users)

Key Pattern: cart:lock:{user_id}
Type: String with TTL (optimistic locking)

Key Pattern: inventory:reserved:{product_id}
Type: String (counter of reserved units)
```

**Why Hash over a single JSON string?**
- HSET/HDEL operate on individual items without read-modify-write
- HGETALL fetches everything in one round-trip
- HINCRBY can update quantity atomically
- Memory-efficient for small carts (ziplist encoding up to 128 fields)

---

### Core Cart Operations

```python
import redis
import json
import time
import uuid

class RedisShoppingCart:
    """
    Production shopping cart backed by Redis Hashes.
    
    Design decisions:
    - Each item stored as a separate Hash field for atomic per-item ops
    - Price stored at add-time (snapshot pricing, not live lookup on checkout)
    - TTL refreshed on every write to keep active carts alive
    """
    
    def __init__(self, redis_client: redis.Redis, cart_ttl: int = 86400 * 7):
        self.r = redis_client
        self.cart_ttl = cart_ttl  # 7 days default
    
    def _cart_key(self, user_id: str) -> str:
        return f"cart:{user_id}"
    
    def add_item(
        self,
        user_id: str,
        product_id: str,
        quantity: int,
        price_cents: int,
        name: str,
        variant: str = None,
    ) -> dict:
        """
        Add item to cart. If item already exists, increments quantity.
        Returns updated item state.
        """
        cart_key = self._cart_key(user_id)
        
        # Check if item already in cart
        existing = self.r.hget(cart_key, product_id)
        
        if existing:
            item = json.loads(existing)
            item["quantity"] += quantity
            item["updated_at"] = time.time()
        else:
            item = {
                "product_id": product_id,
                "name": name,
                "variant": variant,
                "quantity": quantity,
                "price_cents": price_cents,  # Snapshot at add time
                "added_at": time.time(),
                "updated_at": time.time(),
            }
        
        pipe = self.r.pipeline()
        pipe.hset(cart_key, product_id, json.dumps(item))
        pipe.expire(cart_key, self.cart_ttl)  # Refresh TTL on activity
        pipe.execute()
        
        return item
    
    def remove_item(self, user_id: str, product_id: str) -> bool:
        """Remove item entirely from cart. Returns True if item existed."""
        cart_key = self._cart_key(user_id)
        removed = self.r.hdel(cart_key, product_id)
        return removed > 0
    
    def update_quantity(self, user_id: str, product_id: str, quantity: int) -> dict | None:
        """
        Set absolute quantity. If quantity <= 0, removes item.
        Returns updated item or None if not found.
        """
        if quantity <= 0:
            self.remove_item(user_id, product_id)
            return None
        
        cart_key = self._cart_key(user_id)
        existing = self.r.hget(cart_key, product_id)
        
        if not existing:
            return None
        
        item = json.loads(existing)
        item["quantity"] = quantity
        item["updated_at"] = time.time()
        
        pipe = self.r.pipeline()
        pipe.hset(cart_key, product_id, json.dumps(item))
        pipe.expire(cart_key, self.cart_ttl)
        pipe.execute()
        
        return item
    
    def get_cart(self, user_id: str) -> list[dict]:
        """Fetch all items in cart."""
        cart_key = self._cart_key(user_id)
        raw_items = self.r.hgetall(cart_key)
        
        items = []
        for product_id, data in raw_items.items():
            item = json.loads(data)
            items.append(item)
        
        # Sort by added_at for stable ordering
        items.sort(key=lambda x: x["added_at"])
        return items
    
    def get_cart_summary(self, user_id: str) -> dict:
        """Quick summary: total items, total price."""
        items = self.get_cart(user_id)
        total_items = sum(i["quantity"] for i in items)
        total_cents = sum(i["quantity"] * i["price_cents"] for i in items)
        
        return {
            "item_count": len(items),
            "total_items": total_items,
            "total_cents": total_cents,
            "total_display": f"${total_cents / 100:.2f}",
        }
    
    def clear_cart(self, user_id: str) -> int:
        """Delete entire cart. Returns number of items removed."""
        cart_key = self._cart_key(user_id)
        count = self.r.hlen(cart_key)
        self.r.delete(cart_key)
        return count
    
    def cart_item_count(self, user_id: str) -> int:
        """O(1) operation for showing cart badge count."""
        return self.r.hlen(self._cart_key(user_id))
```

---

### Atomic Inventory Reservation

When a user adds an item to cart, you may want to "soft-reserve" inventory to prevent overselling. This must be atomic — two users adding the last item simultaneously should only let one succeed.

```python
class InventoryReserver:
    """
    Atomic inventory reservation using Lua scripts.
    
    Strategy: Decrement available stock and increment reserved count atomically.
    On cart expiration or removal, release reservation.
    
    Keys:
      inventory:{product_id}:available  → current available stock
      inventory:{product_id}:reserved   → total reserved across all carts
      cart:reservations:{user_id}       → Hash of product_id → reserved_qty
    """
    
    RESERVE_SCRIPT = """
    local available_key = KEYS[1]
    local reserved_key = KEYS[2]
    local user_reservations_key = KEYS[3]
    local product_id = ARGV[1]
    local quantity = tonumber(ARGV[2])
    
    local available = tonumber(redis.call('GET', available_key) or '0')
    
    if available < quantity then
        return -1  -- Insufficient stock
    end
    
    -- Atomically: decrement available, increment reserved, track per-user
    redis.call('DECRBY', available_key, quantity)
    redis.call('INCRBY', reserved_key, quantity)
    redis.call('HINCRBY', user_reservations_key, product_id, quantity)
    
    return available - quantity  -- Return remaining available
    """
    
    RELEASE_SCRIPT = """
    local available_key = KEYS[1]
    local reserved_key = KEYS[2]
    local user_reservations_key = KEYS[3]
    local product_id = ARGV[1]
    local quantity = tonumber(ARGV[2])
    
    -- Release: increment available, decrement reserved, reduce user tracking
    redis.call('INCRBY', available_key, quantity)
    redis.call('DECRBY', reserved_key, quantity)
    redis.call('HINCRBY', user_reservations_key, product_id, -quantity)
    
    -- Clean up zero entries
    local remaining = tonumber(redis.call('HGET', user_reservations_key, product_id) or '0')
    if remaining <= 0 then
        redis.call('HDEL', user_reservations_key, product_id)
    end
    
    return 1
    """
    
    def __init__(self, redis_client: redis.Redis, reservation_ttl: int = 900):
        self.r = redis_client
        self.reservation_ttl = reservation_ttl  # 15 min default
    
    def reserve(self, user_id: str, product_id: str, quantity: int) -> bool:
        """
        Attempt to reserve inventory. Returns True if successful.
        Reservation expires if not confirmed (checkout) within TTL.
        """
        keys = [
            f"inventory:{product_id}:available",
            f"inventory:{product_id}:reserved",
            f"cart:reservations:{user_id}",
        ]
        
        result = self.r.execute_command(
            "EVAL", self.RESERVE_SCRIPT, 3,
            *keys, product_id, str(quantity)
        )
        
        if result == -1:
            return False  # Insufficient stock
        
        # Set TTL on user's reservations so they auto-expire
        self.r.expire(f"cart:reservations:{user_id}", self.reservation_ttl)
        return True
    
    def release(self, user_id: str, product_id: str, quantity: int) -> None:
        """Release reserved inventory (item removed from cart or cart expired)."""
        keys = [
            f"inventory:{product_id}:available",
            f"inventory:{product_id}:reserved",
            f"cart:reservations:{user_id}",
        ]
        
        self.r.execute_command(
            "EVAL", self.RELEASE_SCRIPT, 3,
            *keys, product_id, str(quantity)
        )
    
    def release_all_for_user(self, user_id: str) -> None:
        """Release all reservations for a user (cart abandoned/expired)."""
        reservations_key = f"cart:reservations:{user_id}"
        reservations = self.r.hgetall(reservations_key)
        
        for product_id, qty in reservations.items():
            quantity = int(qty)
            if quantity > 0:
                self.release(user_id, product_id.decode() if isinstance(product_id, bytes) else product_id, quantity)
    
    def confirm_reservation(self, user_id: str) -> dict:
        """
        Called at checkout. Converts reservation to sold stock.
        Removes reservation tracking but does NOT restore available count.
        """
        reservations_key = f"cart:reservations:{user_id}"
        reservations = self.r.hgetall(reservations_key)
        
        confirmed = {}
        pipe = self.r.pipeline()
        
        for product_id, qty in reservations.items():
            pid = product_id.decode() if isinstance(product_id, bytes) else product_id
            quantity = int(qty)
            # Decrement reserved count (stock already subtracted from available)
            pipe.decrby(f"inventory:{pid}:reserved", quantity)
            confirmed[pid] = quantity
        
        pipe.delete(reservations_key)
        pipe.execute()
        
        return confirmed
```

---

### Cart Merging: Anonymous → Authenticated

When a guest user logs in, their anonymous cart should merge with any existing authenticated cart.

```python
class CartMerger:
    """
    Handles merging anonymous session cart into authenticated user cart.
    
    Merge strategies:
    1. KEEP_HIGHER_QUANTITY: If same item in both, keep higher quantity
    2. SUM_QUANTITIES: Add quantities together
    3. PREFER_AUTHENTICATED: Keep authenticated cart's item data
    """
    
    MERGE_SCRIPT = """
    local anon_key = KEYS[1]
    local auth_key = KEYS[2]
    local strategy = ARGV[1]
    local ttl = tonumber(ARGV[2])
    
    -- Get all items from anonymous cart
    local anon_items = redis.call('HGETALL', anon_key)
    
    if #anon_items == 0 then
        return 0  -- Nothing to merge
    end
    
    local merged_count = 0
    
    for i = 1, #anon_items, 2 do
        local product_id = anon_items[i]
        local anon_data = anon_items[i + 1]
        local auth_data = redis.call('HGET', auth_key, product_id)
        
        if auth_data then
            -- Item exists in both carts
            local anon_item = cjson.decode(anon_data)
            local auth_item = cjson.decode(auth_data)
            
            if strategy == 'SUM' then
                auth_item['quantity'] = auth_item['quantity'] + anon_item['quantity']
                redis.call('HSET', auth_key, product_id, cjson.encode(auth_item))
            elseif strategy == 'MAX' then
                if anon_item['quantity'] > auth_item['quantity'] then
                    auth_item['quantity'] = anon_item['quantity']
                    redis.call('HSET', auth_key, product_id, cjson.encode(auth_item))
                end
            end
            -- PREFER_AUTH: do nothing, keep existing
        else
            -- Item only in anonymous cart, add to authenticated
            redis.call('HSET', auth_key, product_id, anon_data)
        end
        
        merged_count = merged_count + 1
    end
    
    -- Delete anonymous cart after merge
    redis.call('DEL', anon_key)
    
    -- Refresh TTL on merged cart
    redis.call('EXPIRE', auth_key, ttl)
    
    return merged_count
    """
    
    def __init__(self, redis_client: redis.Redis, cart_ttl: int = 86400 * 7):
        self.r = redis_client
        self.cart_ttl = cart_ttl
    
    def merge_carts(
        self,
        session_id: str,
        user_id: str,
        strategy: str = "MAX",
    ) -> int:
        """
        Merge anonymous cart into authenticated cart.
        
        Args:
            session_id: Anonymous session identifier
            user_id: Authenticated user ID
            strategy: 'SUM' | 'MAX' | 'PREFER_AUTH'
        
        Returns: Number of items processed from anonymous cart
        """
        anon_key = f"cart:anon:{session_id}"
        auth_key = f"cart:{user_id}"
        
        result = self.r.execute_command(
            "EVAL", self.MERGE_SCRIPT, 2,
            anon_key, auth_key,
            strategy, str(self.cart_ttl)
        )
        
        return int(result)
```

---

### Cart Expiration & Abandoned Cart Recovery

```python
import redis

class AbandonedCartTracker:
    """
    Track carts for abandoned cart email campaigns.
    
    Architecture:
    - Sorted Set keyed by last-activity timestamp
    - When cart activity occurs, update score
    - Background worker scans for carts idle > threshold
    
    Key: abandoned:carts (Sorted Set, score = last_activity_timestamp)
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.r = redis_client
        self.tracker_key = "abandoned:carts"
    
    def record_activity(self, user_id: str) -> None:
        """Called on every cart modification to update last-activity time."""
        self.r.zadd(self.tracker_key, {user_id: time.time()})
    
    def remove_user(self, user_id: str) -> None:
        """Called on checkout or explicit cart clear."""
        self.r.zrem(self.tracker_key, user_id)
    
    def get_abandoned_carts(
        self,
        idle_threshold_seconds: int = 3600,
        limit: int = 100,
    ) -> list[str]:
        """
        Find carts that have been idle for longer than threshold.
        Returns list of user_ids with abandoned carts.
        
        Uses ZRANGEBYSCORE to find users whose last activity
        is older than (now - threshold).
        """
        cutoff = time.time() - idle_threshold_seconds
        
        # Score represents last activity time
        # We want users with score < cutoff (idle for too long)
        user_ids = self.r.zrangebyscore(
            self.tracker_key,
            "-inf",
            cutoff,
            start=0,
            num=limit,
        )
        
        return [uid.decode() if isinstance(uid, bytes) else uid for uid in user_ids]
    
    def get_abandoned_cart_with_details(
        self,
        idle_threshold_seconds: int = 3600,
        limit: int = 50,
    ) -> list[dict]:
        """Get abandoned carts with their contents for email campaigns."""
        user_ids = self.get_abandoned_carts(idle_threshold_seconds, limit)
        
        results = []
        pipe = self.r.pipeline()
        
        for user_id in user_ids:
            pipe.hgetall(f"cart:{user_id}")
        
        cart_data = pipe.execute()
        
        for user_id, raw_items in zip(user_ids, cart_data):
            if not raw_items:
                # Cart expired since we queried the sorted set
                self.remove_user(user_id)
                continue
            
            items = [json.loads(v) for v in raw_items.values()]
            total_cents = sum(i["quantity"] * i["price_cents"] for i in items)
            
            results.append({
                "user_id": user_id,
                "items": items,
                "total_cents": total_cents,
                "item_count": len(items),
            })
        
        return results
```

---

### Cart with Optimistic Locking (WATCH/MULTI)

For scenarios where you need read-modify-write consistency across concurrent tabs:

```python
class OptimisticCart:
    """
    Uses Redis WATCH for optimistic concurrency control.
    
    When: User has multiple browser tabs open and modifies cart
    simultaneously. Without WATCH, a read-modify-write in one tab
    could overwrite changes from another tab.
    
    WATCH monitors the key — if it changes between WATCH and EXEC,
    the transaction fails and we retry.
    """
    
    def __init__(self, redis_client: redis.Redis, max_retries: int = 3):
        self.r = redis_client
        self.max_retries = max_retries
    
    def apply_coupon_to_cart(self, user_id: str, discount_percent: int) -> bool:
        """
        Apply percentage discount to all items in cart.
        Uses WATCH to prevent concurrent coupon applications.
        """
        cart_key = f"cart:{user_id}"
        
        for attempt in range(self.max_retries):
            try:
                with self.r.pipeline() as pipe:
                    pipe.watch(cart_key)
                    
                    # Read current state (outside MULTI)
                    raw_items = pipe.hgetall(cart_key)
                    
                    if not raw_items:
                        return False
                    
                    # Compute new prices
                    updated = {}
                    for product_id, data in raw_items.items():
                        item = json.loads(data)
                        original = item.get("original_price_cents", item["price_cents"])
                        item["original_price_cents"] = original
                        item["price_cents"] = int(original * (100 - discount_percent) / 100)
                        item["discount_applied"] = discount_percent
                        updated[product_id] = json.dumps(item)
                    
                    # Execute atomically — fails if cart_key changed since WATCH
                    pipe.multi()
                    for product_id, data in updated.items():
                        pipe.hset(cart_key, product_id, data)
                    pipe.execute()
                    
                    return True
                    
            except redis.WatchError:
                # Another client modified the cart, retry
                continue
        
        return False  # Exhausted retries
```

---

## Part 2: Feature Flags with Redis

### Why Redis for Feature Flags?

Feature flags need:
- **Ultra-low latency reads** — checked on every request
- **Real-time updates** — flip a flag, all servers see it instantly
- **No deployment required** — operational control at runtime
- **Rich targeting** — percentage rollouts, user segments, environments

Redis provides all of this with sub-millisecond reads and Pub/Sub for propagation.

---

### Data Model

```
Key Pattern: ff:{flag_name}               → Hash (flag configuration)
Key Pattern: ff:{flag_name}:users         → Set (explicitly enabled user IDs)
Key Pattern: ff:{flag_name}:segments      → Set (enabled segment names)
Key Pattern: ff:overrides:{user_id}       → Hash (per-user flag overrides)
Key Pattern: ff:index                     → Set (all registered flag names)
Key Pattern: ff:changelog                 → Stream (audit log of changes)
```

**Flag Hash Structure:**
```
{
  "enabled": "true" | "false",
  "rollout_percentage": "0" to "100",
  "strategy": "boolean" | "percentage" | "segment" | "gradual",
  "created_at": timestamp,
  "updated_at": timestamp,
  "description": "human-readable purpose",
  "owner": "team or person",
  "kill_switch": "false",
}
```

---

### Feature Flag Engine

```python
import redis
import hashlib
import time
import json

class FeatureFlagEngine:
    """
    Production feature flag system backed by Redis.
    
    Evaluation order (first match wins):
    1. Kill switch — if ON, flag is always OFF for everyone
    2. Per-user override — explicit enable/disable for specific users
    3. User segment — check if user belongs to an enabled segment
    4. Percentage rollout — deterministic hash-based allocation
    5. Default state — flag's base enabled/disabled state
    
    Deterministic rollout: Uses consistent hashing (user_id + flag_name)
    so the same user always gets the same result for a given percentage,
    and increasing the percentage never removes previously-included users.
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.r = redis_client
    
    def create_flag(
        self,
        flag_name: str,
        enabled: bool = False,
        rollout_percentage: int = 0,
        strategy: str = "boolean",
        description: str = "",
        owner: str = "",
    ) -> None:
        """Register a new feature flag."""
        flag_key = f"ff:{flag_name}"
        
        flag_data = {
            "enabled": str(enabled).lower(),
            "rollout_percentage": str(rollout_percentage),
            "strategy": strategy,
            "description": description,
            "owner": owner,
            "kill_switch": "false",
            "created_at": str(time.time()),
            "updated_at": str(time.time()),
        }
        
        pipe = self.r.pipeline()
        pipe.hset(flag_key, mapping=flag_data)
        pipe.sadd("ff:index", flag_name)
        pipe.execute()
        
        self._audit_log(flag_name, "created", flag_data)
    
    def is_enabled(
        self,
        flag_name: str,
        user_id: str = None,
        user_segments: list[str] = None,
        default: bool = False,
    ) -> bool:
        """
        Evaluate whether a feature flag is enabled for the given context.
        
        This is the hot path — called on every request. Optimized for
        minimal Redis round-trips using pipeline.
        """
        flag_key = f"ff:{flag_name}"
        
        # Single pipeline to fetch all needed data
        pipe = self.r.pipeline()
        pipe.hgetall(flag_key)
        
        if user_id:
            pipe.hget(f"ff:overrides:{user_id}", flag_name)
            pipe.sismember(f"ff:{flag_name}:users", user_id)
        
        results = pipe.execute()
        flag_config = results[0]
        
        # Flag doesn't exist
        if not flag_config:
            return default
        
        # Decode bytes if needed
        config = {
            (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
            for k, v in flag_config.items()
        }
        
        # 1. Kill switch
        if config.get("kill_switch") == "true":
            return False
        
        # 2. Per-user override
        if user_id:
            override = results[1]
            if override is not None:
                override_val = override.decode() if isinstance(override, bytes) else override
                return override_val == "true"
            
            # 3. Explicitly enabled users
            is_explicit_user = results[2]
            if is_explicit_user:
                return True
        
        # 4. Segment check
        if user_segments and config.get("strategy") == "segment":
            flag_segments = self.r.smembers(f"ff:{flag_name}:segments")
            flag_segments = {s.decode() if isinstance(s, bytes) else s for s in flag_segments}
            if flag_segments.intersection(set(user_segments)):
                return True
        
        # 5. Percentage rollout
        if config.get("strategy") == "percentage" and user_id:
            percentage = int(config.get("rollout_percentage", "0"))
            return self._is_in_percentage(flag_name, user_id, percentage)
        
        # 6. Gradual rollout (percentage + boolean combined)
        if config.get("strategy") == "gradual" and user_id:
            if config.get("enabled") != "true":
                return False
            percentage = int(config.get("rollout_percentage", "0"))
            return self._is_in_percentage(flag_name, user_id, percentage)
        
        # 7. Default boolean state
        return config.get("enabled") == "true"
    
    def _is_in_percentage(self, flag_name: str, user_id: str, percentage: int) -> bool:
        """
        Deterministic percentage allocation using consistent hashing.
        
        Properties:
        - Same user always gets same result for same flag + percentage
        - Increasing percentage from 30→50 keeps all previous 30% users included
        - Different flags give different allocations (no correlation)
        """
        if percentage >= 100:
            return True
        if percentage <= 0:
            return False
        
        # Hash user_id + flag_name for deterministic, uncorrelated allocation
        hash_input = f"{user_id}:{flag_name}"
        hash_value = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)
        bucket = hash_value % 100
        
        return bucket < percentage
    
    def set_rollout_percentage(self, flag_name: str, percentage: int) -> None:
        """Update rollout percentage (0-100)."""
        flag_key = f"ff:{flag_name}"
        pipe = self.r.pipeline()
        pipe.hset(flag_key, "rollout_percentage", str(percentage))
        pipe.hset(flag_key, "updated_at", str(time.time()))
        pipe.execute()
        
        self._audit_log(flag_name, "percentage_updated", {"percentage": percentage})
    
    def enable_for_user(self, flag_name: str, user_id: str) -> None:
        """Explicitly enable flag for a specific user (beta testers, etc.)."""
        self.r.sadd(f"ff:{flag_name}:users", user_id)
        self._audit_log(flag_name, "user_enabled", {"user_id": user_id})
    
    def disable_for_user(self, flag_name: str, user_id: str) -> None:
        """Explicitly disable flag for a specific user."""
        self.r.hset(f"ff:overrides:{user_id}", flag_name, "false")
        self._audit_log(flag_name, "user_disabled", {"user_id": user_id})
    
    def enable_for_segment(self, flag_name: str, segment: str) -> None:
        """Enable flag for all users in a segment (e.g., 'beta', 'enterprise')."""
        self.r.sadd(f"ff:{flag_name}:segments", segment)
        self._audit_log(flag_name, "segment_enabled", {"segment": segment})
    
    def activate_kill_switch(self, flag_name: str) -> None:
        """
        Emergency kill switch. Immediately disables flag for ALL users,
        overriding all other rules including explicit enables.
        """
        pipe = self.r.pipeline()
        pipe.hset(f"ff:{flag_name}", "kill_switch", "true")
        pipe.hset(f"ff:{flag_name}", "updated_at", str(time.time()))
        pipe.execute()
        
        self._audit_log(flag_name, "kill_switch_activated", {})
    
    def deactivate_kill_switch(self, flag_name: str) -> None:
        """Restore normal evaluation after kill switch."""
        pipe = self.r.pipeline()
        pipe.hset(f"ff:{flag_name}", "kill_switch", "false")
        pipe.hset(f"ff:{flag_name}", "updated_at", str(time.time()))
        pipe.execute()
        
        self._audit_log(flag_name, "kill_switch_deactivated", {})
    
    def _audit_log(self, flag_name: str, action: str, details: dict) -> None:
        """Append to audit stream for compliance and debugging."""
        self.r.xadd("ff:changelog", {
            "flag": flag_name,
            "action": action,
            "details": json.dumps(details),
            "timestamp": str(time.time()),
        }, maxlen=10000)
    
    def list_flags(self) -> list[dict]:
        """List all registered flags with their configuration."""
        flag_names = self.r.smembers("ff:index")
        
        pipe = self.r.pipeline()
        decoded_names = []
        for name in flag_names:
            decoded = name.decode() if isinstance(name, bytes) else name
            decoded_names.append(decoded)
            pipe.hgetall(f"ff:{decoded}")
        
        configs = pipe.execute()
        
        results = []
        for name, config in zip(decoded_names, configs):
            decoded_config = {
                (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
                for k, v in config.items()
            }
            decoded_config["name"] = name
            results.append(decoded_config)
        
        return results
```

---

### Gradual Rollout Controller

```python
class GradualRollout:
    """
    Manages progressive rollout: 1% → 5% → 10% → 25% → 50% → 100%
    
    Provides safety checks between stages:
    - Error rate monitoring
    - Latency degradation detection
    - Automatic rollback if thresholds exceeded
    """
    
    STAGES = [1, 5, 10, 25, 50, 75, 100]
    
    def __init__(self, redis_client: redis.Redis, flag_engine: FeatureFlagEngine):
        self.r = redis_client
        self.engine = flag_engine
    
    def start_rollout(self, flag_name: str) -> dict:
        """Begin gradual rollout at first stage (1%)."""
        state = {
            "flag_name": flag_name,
            "current_stage": 0,
            "percentage": self.STAGES[0],
            "started_at": time.time(),
            "stage_started_at": time.time(),
            "status": "active",
        }
        
        self.r.hset(f"ff:rollout:{flag_name}", mapping={
            k: str(v) for k, v in state.items()
        })
        
        self.engine.set_rollout_percentage(flag_name, self.STAGES[0])
        return state
    
    def advance_stage(self, flag_name: str) -> dict | None:
        """
        Advance to next rollout stage.
        Returns new state, or None if already at 100%.
        """
        rollout_key = f"ff:rollout:{flag_name}"
        state = self.r.hgetall(rollout_key)
        
        if not state:
            return None
        
        current_stage = int(state.get(b"current_stage", state.get("current_stage", 0)))
        next_stage = current_stage + 1
        
        if next_stage >= len(self.STAGES):
            # Already at max
            self.r.hset(rollout_key, "status", "complete")
            return None
        
        new_percentage = self.STAGES[next_stage]
        
        pipe = self.r.pipeline()
        pipe.hset(rollout_key, "current_stage", str(next_stage))
        pipe.hset(rollout_key, "percentage", str(new_percentage))
        pipe.hset(rollout_key, "stage_started_at", str(time.time()))
        pipe.execute()
        
        self.engine.set_rollout_percentage(flag_name, new_percentage)
        
        return {
            "flag_name": flag_name,
            "stage": next_stage,
            "percentage": new_percentage,
        }
    
    def rollback(self, flag_name: str) -> None:
        """Emergency rollback — disable flag entirely."""
        self.engine.activate_kill_switch(flag_name)
        self.r.hset(f"ff:rollout:{flag_name}", "status", "rolled_back")
    
    def check_health_and_advance(
        self,
        flag_name: str,
        error_rate: float,
        p99_latency_ms: float,
        error_threshold: float = 0.05,
        latency_threshold_ms: float = 500,
        min_stage_duration_seconds: int = 300,
    ) -> str:
        """
        Automated advancement/rollback based on health metrics.
        
        Returns: 'advanced' | 'holding' | 'rolled_back'
        """
        rollout_key = f"ff:rollout:{flag_name}"
        state = self.r.hgetall(rollout_key)
        
        if not state:
            return "holding"
        
        # Decode state
        stage_started = float(state.get(b"stage_started_at", state.get("stage_started_at", 0)))
        status = (state.get(b"status", state.get("status", b"active")))
        if isinstance(status, bytes):
            status = status.decode()
        
        if status != "active":
            return "holding"
        
        # Check error rate
        if error_rate > error_threshold:
            self.rollback(flag_name)
            return "rolled_back"
        
        # Check latency
        if p99_latency_ms > latency_threshold_ms:
            self.rollback(flag_name)
            return "rolled_back"
        
        # Check minimum bake time
        elapsed = time.time() - stage_started
        if elapsed < min_stage_duration_seconds:
            return "holding"
        
        # Safe to advance
        result = self.advance_stage(flag_name)
        return "advanced" if result else "holding"
```

---

### A/B Testing with Feature Flags

```python
class ABTestEngine:
    """
    A/B testing built on the feature flag infrastructure.
    
    Each experiment has N variants. Users are deterministically assigned
    to a variant using consistent hashing. Results are tracked in Redis
    for real-time dashboards, then exported to analytics for significance testing.
    
    Keys:
      ab:{experiment}:config      → Hash (variants, weights, status)
      ab:{experiment}:assignments → Hash (user_id → variant)
      ab:{experiment}:metrics:{variant} → Hash (metric_name → value)
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.r = redis_client
    
    def create_experiment(
        self,
        experiment_name: str,
        variants: list[dict],
        description: str = "",
    ) -> None:
        """
        Create A/B experiment.
        
        Args:
            variants: [{"name": "control", "weight": 50}, {"name": "variant_a", "weight": 50}]
                      Weights must sum to 100.
        """
        total_weight = sum(v["weight"] for v in variants)
        assert total_weight == 100, f"Weights must sum to 100, got {total_weight}"
        
        config = {
            "variants": json.dumps(variants),
            "description": description,
            "status": "active",
            "created_at": str(time.time()),
            "total_assignments": "0",
        }
        
        self.r.hset(f"ab:{experiment_name}:config", mapping=config)
    
    def get_variant(self, experiment_name: str, user_id: str) -> str | None:
        """
        Get user's variant assignment. Creates assignment if first visit.
        
        Assignment is sticky — once assigned, always returns same variant.
        Uses consistent hashing for new assignments (deterministic).
        """
        config_key = f"ab:{experiment_name}:config"
        assignments_key = f"ab:{experiment_name}:assignments"
        
        # Check existing assignment first (most common path)
        existing = self.r.hget(assignments_key, user_id)
        if existing:
            return existing.decode() if isinstance(existing, bytes) else existing
        
        # Load experiment config
        config = self.r.hgetall(config_key)
        if not config:
            return None
        
        status = config.get(b"status", config.get("status", b""))
        if isinstance(status, bytes):
            status = status.decode()
        if status != "active":
            return None
        
        variants_raw = config.get(b"variants", config.get("variants", b"[]"))
        if isinstance(variants_raw, bytes):
            variants_raw = variants_raw.decode()
        variants = json.loads(variants_raw)
        
        # Deterministic assignment using consistent hashing
        hash_input = f"{user_id}:{experiment_name}"
        hash_value = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)
        bucket = hash_value % 100
        
        cumulative = 0
        assigned_variant = variants[-1]["name"]  # fallback
        for variant in variants:
            cumulative += variant["weight"]
            if bucket < cumulative:
                assigned_variant = variant["name"]
                break
        
        # Persist assignment (sticky)
        pipe = self.r.pipeline()
        pipe.hset(assignments_key, user_id, assigned_variant)
        pipe.hincrby(config_key, "total_assignments", 1)
        pipe.execute()
        
        return assigned_variant
    
    def record_conversion(
        self,
        experiment_name: str,
        user_id: str,
        metric_name: str = "conversion",
        value: float = 1.0,
    ) -> None:
        """
        Record a conversion event for the user's assigned variant.
        
        Common metrics: 'conversion', 'revenue_cents', 'click_through', 'time_on_page_ms'
        """
        variant = self.get_variant(experiment_name, user_id)
        if not variant:
            return
        
        metrics_key = f"ab:{experiment_name}:metrics:{variant}"
        
        pipe = self.r.pipeline()
        pipe.hincrbyfloat(metrics_key, f"{metric_name}:sum", value)
        pipe.hincrby(metrics_key, f"{metric_name}:count", 1)
        pipe.execute()
    
    def get_results(self, experiment_name: str) -> dict:
        """Get current experiment results across all variants."""
        config = self.r.hgetall(f"ab:{experiment_name}:config")
        if not config:
            return {}
        
        variants_raw = config.get(b"variants", config.get("variants", b"[]"))
        if isinstance(variants_raw, bytes):
            variants_raw = variants_raw.decode()
        variants = json.loads(variants_raw)
        
        results = {}
        pipe = self.r.pipeline()
        
        for variant in variants:
            pipe.hgetall(f"ab:{experiment_name}:metrics:{variant['name']}")
        
        metrics_data = pipe.execute()
        
        for variant, metrics in zip(variants, metrics_data):
            decoded_metrics = {
                (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
                for k, v in metrics.items()
            }
            
            results[variant["name"]] = {
                "weight": variant["weight"],
                "metrics": decoded_metrics,
            }
        
        return results
    
    def stop_experiment(self, experiment_name: str, winning_variant: str) -> None:
        """End experiment and lock in the winning variant."""
        self.r.hset(f"ab:{experiment_name}:config", mapping={
            "status": "completed",
            "winner": winning_variant,
            "completed_at": str(time.time()),
        })
```

---

### Circuit Breaker with Feature Flags

```python
class CircuitBreakerFlag:
    """
    Combines feature flags with circuit breaker pattern.
    
    When an external dependency starts failing, automatically disable
    the feature that depends on it. Prevents cascading failures.
    
    States:
    - CLOSED: Feature enabled, tracking error rate
    - OPEN: Feature disabled (circuit tripped), waiting for recovery
    - HALF_OPEN: Allowing limited traffic through to test recovery
    """
    
    CIRCUIT_EVAL_SCRIPT = """
    local breaker_key = KEYS[1]
    local flag_key = KEYS[2]
    local action = ARGV[1]
    local threshold = tonumber(ARGV[2])
    local window_size = tonumber(ARGV[3])
    local now = tonumber(ARGV[4])
    
    if action == 'record_failure' then
        -- Add failure timestamp to sliding window
        redis.call('ZADD', breaker_key, now, now .. ':' .. math.random(1000000))
        -- Remove entries outside window
        redis.call('ZREMRANGEBYSCORE', breaker_key, '-inf', now - window_size)
        -- Count failures in window
        local failure_count = redis.call('ZCARD', breaker_key)
        
        if failure_count >= threshold then
            -- Trip the circuit
            redis.call('HSET', flag_key, 'kill_switch', 'true')
            redis.call('HSET', flag_key, 'circuit_state', 'open')
            redis.call('HSET', flag_key, 'circuit_opened_at', tostring(now))
            return 'OPENED'
        end
        return 'CLOSED'
        
    elseif action == 'record_success' then
        -- On success in half-open state, close the circuit
        local state = redis.call('HGET', flag_key, 'circuit_state')
        if state == 'half_open' then
            redis.call('HSET', flag_key, 'kill_switch', 'false')
            redis.call('HSET', flag_key, 'circuit_state', 'closed')
            redis.call('DEL', breaker_key)
            return 'CLOSED'
        end
        return state or 'CLOSED'
    end
    
    return 'UNKNOWN'
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        flag_name: str,
        failure_threshold: int = 10,
        window_seconds: int = 60,
        recovery_timeout: int = 30,
    ):
        self.r = redis_client
        self.flag_name = flag_name
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.recovery_timeout = recovery_timeout
        self.breaker_key = f"ff:circuit:{flag_name}:failures"
        self.flag_key = f"ff:{flag_name}"
    
    def record_failure(self) -> str:
        """Record a failure. May trip the circuit. Returns new state."""
        result = self.r.execute_command(
            "EVAL", self.CIRCUIT_EVAL_SCRIPT, 2,
            self.breaker_key, self.flag_key,
            "record_failure",
            str(self.failure_threshold),
            str(self.window_seconds),
            str(time.time()),
        )
        return result.decode() if isinstance(result, bytes) else result
    
    def record_success(self) -> str:
        """Record a success. May close circuit if in half-open state."""
        result = self.r.execute_command(
            "EVAL", self.CIRCUIT_EVAL_SCRIPT, 2,
            self.breaker_key, self.flag_key,
            "record_success",
            str(self.failure_threshold),
            str(self.window_seconds),
            str(time.time()),
        )
        return result.decode() if isinstance(result, bytes) else result
    
    def attempt_recovery(self) -> bool:
        """
        Called periodically. If circuit has been open long enough,
        transition to half-open to allow a probe request.
        """
        state = self.r.hget(self.flag_key, "circuit_state")
        if not state:
            return False
        
        state = state.decode() if isinstance(state, bytes) else state
        if state != "open":
            return False
        
        opened_at = self.r.hget(self.flag_key, "circuit_opened_at")
        if not opened_at:
            return False
        
        opened_at = float(opened_at.decode() if isinstance(opened_at, bytes) else opened_at)
        
        if time.time() - opened_at >= self.recovery_timeout:
            # Transition to half-open: allow limited traffic
            self.r.hset(self.flag_key, "circuit_state", "half_open")
            self.r.hset(self.flag_key, "kill_switch", "false")
            # Set low rollout to probe
            self.r.hset(self.flag_key, "rollout_percentage", "5")
            return True
        
        return False
```

---

### Local Cache + Redis (Two-Layer Flag Evaluation)

In production, you don't want a Redis round-trip for every request. Use a local in-memory cache with Redis Pub/Sub for invalidation.

```python
import threading

class CachedFeatureFlags:
    """
    Two-layer caching for feature flag evaluation:
    
    Layer 1: In-process dictionary (0 latency, stale up to refresh interval)
    Layer 2: Redis (sub-ms latency, always fresh)
    
    Cache invalidation via Redis Pub/Sub — when a flag changes,
    all application instances get notified and refresh their local cache.
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        flag_engine: FeatureFlagEngine,
        refresh_interval: int = 30,
    ):
        self.r = redis_client
        self.engine = flag_engine
        self.refresh_interval = refresh_interval
        self._cache: dict[str, dict] = {}
        self._cache_lock = threading.Lock()
        self._last_refresh = 0
    
    def is_enabled(self, flag_name: str, user_id: str = None, **kwargs) -> bool:
        """
        Check flag with local cache. Falls through to Redis on miss.
        """
        # Check if cache needs refresh
        if time.time() - self._last_refresh > self.refresh_interval:
            self._refresh_cache()
        
        # Fast path: flag config in local cache
        with self._cache_lock:
            config = self._cache.get(flag_name)
        
        if config is None:
            # Cache miss — fetch from Redis and cache
            return self.engine.is_enabled(flag_name, user_id, **kwargs)
        
        # Evaluate locally for simple cases
        if config.get("kill_switch") == "true":
            return False
        
        if config.get("strategy") == "boolean":
            return config.get("enabled") == "true"
        
        # Complex evaluation still goes to Redis (segments, overrides)
        return self.engine.is_enabled(flag_name, user_id, **kwargs)
    
    def _refresh_cache(self) -> None:
        """Bulk-load all flag configs into local cache."""
        flag_names = self.r.smembers("ff:index")
        
        pipe = self.r.pipeline()
        decoded_names = []
        for name in flag_names:
            decoded = name.decode() if isinstance(name, bytes) else name
            decoded_names.append(decoded)
            pipe.hgetall(f"ff:{decoded}")
        
        configs = pipe.execute()
        
        new_cache = {}
        for name, config in zip(decoded_names, configs):
            new_cache[name] = {
                (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
                for k, v in config.items()
            }
        
        with self._cache_lock:
            self._cache = new_cache
            self._last_refresh = time.time()
    
    def start_invalidation_listener(self) -> None:
        """
        Subscribe to flag change notifications.
        When any flag changes, immediately refresh local cache.
        """
        def _listener():
            pubsub = self.r.pubsub()
            pubsub.subscribe("ff:changes")
            
            for message in pubsub.listen():
                if message["type"] == "message":
                    # Flag changed — invalidate cache
                    self._refresh_cache()
        
        thread = threading.Thread(target=_listener, daemon=True)
        thread.start()
    
    def notify_change(self, flag_name: str) -> None:
        """Publish change notification to all instances."""
        self.r.publish("ff:changes", flag_name)
```

---

### Usage Examples

```python
# Initialize
r = redis.Redis(host="localhost", port=6379, db=0)
cart = RedisShoppingCart(r)
flags = FeatureFlagEngine(r)
ab_test = ABTestEngine(r)

# --- Shopping Cart ---
cart.add_item("user:123", "prod:456", quantity=2, price_cents=1999, name="Widget Pro")
cart.add_item("user:123", "prod:789", quantity=1, price_cents=4999, name="Gadget Max")
summary = cart.get_cart_summary("user:123")
# {'item_count': 2, 'total_items': 3, 'total_cents': 8997, 'total_display': '$89.97'}

# --- Feature Flags ---
flags.create_flag("new_checkout_flow", strategy="percentage", rollout_percentage=10)
flags.enable_for_segment("new_checkout_flow", "beta_testers")

if flags.is_enabled("new_checkout_flow", user_id="user:123", user_segments=["beta_testers"]):
    # Show new checkout
    pass

# --- A/B Test ---
ab_test.create_experiment("checkout_button_color", [
    {"name": "control", "weight": 50},
    {"name": "green_button", "weight": 25},
    {"name": "orange_button", "weight": 25},
])

variant = ab_test.get_variant("checkout_button_color", "user:123")
# Returns: "control", "green_button", or "orange_button" (sticky)

ab_test.record_conversion("checkout_button_color", "user:123", "purchase", value=49.99)
```

---

### Production Considerations

| Concern | Shopping Cart | Feature Flags |
|---------|--------------|---------------|
| **Memory** | Set maxmemory-policy to `volatile-lru`; carts have TTL | Flags are small, no eviction concern |
| **Persistence** | AOF with `appendfsync everysec` — lose max 1s of carts | RDB snapshots sufficient; flags are recreated on deploy |
| **Replication** | Read replicas for cart reads in checkout flow | Read replicas for flag evaluation (eventual consistency OK) |
| **Cluster** | Shard by user_id (all cart keys for user on same shard) | Small dataset, single node or replicated |
| **Monitoring** | Alert on cart:* key count growth, memory usage | Alert on kill switch activations, rollout failures |
| **Backup** | Carts are ephemeral — DB of record is order service | Export flag state to version control nightly |

---

### Key Takeaways

1. **Hashes for Carts**: Each item is a field — enables atomic per-item operations without serialization overhead
2. **Lua for Inventory**: Atomic check-and-decrement prevents overselling under concurrent load
3. **Consistent Hashing for Rollouts**: Increasing percentage never removes previously-included users
4. **Kill Switch Priority**: Always evaluate first — enables instant incident response
5. **Two-Layer Cache**: Local memory + Redis Pub/Sub invalidation eliminates per-request latency for flags
6. **Circuit Breaker Integration**: Auto-disable features when their dependencies fail
7. **Sticky Assignments**: A/B test users always see the same variant (stored in Redis Hash)
