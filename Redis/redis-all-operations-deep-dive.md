# Redis Operations Deep Dive — Every Data Type, Every Command

## Table of Contents
1. [Strings](#1-strings)
2. [Hashes](#2-hashes)
3. [Lists](#3-lists)
4. [Sets](#4-sets)
5. [Sorted Sets (ZSets)](#5-sorted-sets-zsets)
6. [Bitmaps](#6-bitmaps)
7. [HyperLogLog](#7-hyperloglog)
8. [Streams](#8-streams)
9. [Keys & Expiry Management](#9-keys--expiry-management)
10. [Transactions & Pipelines](#10-transactions--pipelines)
11. [Atomic Increment Operations](#11-atomic-increment-operations)
12. [Locking & Distributed Locks](#12-locking--distributed-locks)
13. [Lua Scripting](#13-lua-scripting)
14. [Pub/Sub](#14-pubsub)
15. [Geospatial](#15-geospatial)

---

## 1. Strings

Strings are the simplest Redis data type — a key mapped to a binary-safe value (up to 512 MB).
Internally, Redis uses three encodings:
- **int** — if the value is an integer ≤ 2^63-1
- **embstr** — strings ≤ 44 bytes (one allocation, immutable)
- **raw** — strings > 44 bytes (two allocations, mutable)

### 1.1 SET — Store a Value

```python
import redis

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Basic SET
r.set("user:1001:name", "Alice")

# SET with expiry (seconds)
r.set("session:abc123", "user_data_json", ex=3600)

# SET with expiry (milliseconds)
r.set("otp:phone:9876543210", "482910", px=300000)

# SET only if key does NOT exist (NX) — used for locking
was_set = r.set("lock:order:5001", "worker-1", nx=True, ex=30)
# Returns True if set, None if key already existed

# SET only if key ALREADY exists (XX) — update without creating
r.set("user:1001:name", "Alice Smith", xx=True)

# EXAT — expire at absolute Unix timestamp (seconds)
import time
expire_at = int(time.time()) + 86400  # 24 hours from now
r.set("promo:banner", "summer_sale", exat=expire_at)

# PXAT — expire at absolute Unix timestamp (milliseconds)
r.set("flash:deal", "50_off", pxat=int(time.time() * 1000) + 60000)

# KEEPTTL — preserve existing TTL on update
r.set("user:token", "old_value", ex=600)
r.set("user:token", "new_value", keepttl=True)  # TTL remains ~600s
```

**Time Complexity**: O(1)

**Key Insight**: `SET key value NX EX 30` is the foundation of distributed locking — atomic "set if not exists with expiry."

### 1.2 GET — Retrieve a Value

```python
name = r.get("user:1001:name")   # "Alice Smith"
missing = r.get("nonexistent")    # None

# GET returns None for missing keys, not an error
# This is important for cache-aside pattern:
cached = r.get(f"cache:product:{product_id}")
if cached is None:
    data = fetch_from_database(product_id)
    r.set(f"cache:product:{product_id}", json.dumps(data), ex=300)
```

**Time Complexity**: O(1)

### 1.3 MSET / MGET — Batch Operations

```python
# MSET — set multiple keys atomically (all-or-nothing)
r.mset({
    "user:1001:name": "Alice",
    "user:1001:email": "alice@example.com",
    "user:1001:city": "Mumbai"
})

# MGET — get multiple keys in one round trip
values = r.mget("user:1001:name", "user:1001:email", "user:1001:city")
# ["Alice", "alice@example.com", "Mumbai"]

# Missing keys return None in the list
values = r.mget("user:1001:name", "nonexistent", "user:1001:city")
# ["Alice", None, "Mumbai"]
```

**Time Complexity**: O(N) where N = number of keys

**Why MGET matters**: A single MGET for 100 keys = 1 network round trip. 100 individual GETs = 100 round trips. At 0.5ms RTT, that's 0.5ms vs 50ms.

### 1.4 GETSET (deprecated) → GETDEL / GETEX

```python
# GETDEL — get value and delete the key atomically
# Use case: consume a one-time token
token_value = r.getdel("otp:user:1001")
# Returns the value, key is now gone

# GETEX — get value and set/update expiry atomically
# Use case: extend session TTL on access
session = r.getex("session:abc123", ex=3600)
# Returns session data, TTL reset to 3600s

# GETEX with PERSIST — remove expiry
r.getex("session:abc123", persist=True)  # Key now never expires
```

### 1.5 APPEND / STRLEN

```python
# APPEND — append to existing string (or create if missing)
r.set("log:request:001", "2026-01-15T10:00:00 GET /api/users")
r.append("log:request:001", "\n2026-01-15T10:00:01 POST /api/orders")
# Now contains both lines

new_length = r.append("log:request:001", "\n2026-01-15T10:00:02 GET /api/health")
# Returns total length after append

# STRLEN — get byte length of string
length = r.strlen("log:request:001")  # Returns byte count
```

**Time Complexity**: APPEND is O(1) amortized. STRLEN is O(1).

### 1.6 SETRANGE / GETRANGE — Substring Operations

```python
# SETRANGE — overwrite part of a string at offset
r.set("greeting", "Hello, World!")
r.setrange("greeting", 7, "Redis!")
# "Hello, Redis!"

# GETRANGE — get substring (inclusive start and end)
r.set("alphabet", "abcdefghijklmnopqrstuvwxyz")
subset = r.getrange("alphabet", 0, 4)   # "abcde"
subset = r.getrange("alphabet", -3, -1)  # "xyz"
```

### 1.7 SETNX (Legacy) vs SET NX

```python
# SETNX — Set if Not eXists (legacy, DO NOT use for locking alone)
# Problem: SETNX + EXPIRE is two commands, not atomic!
r.setnx("key", "value")  # Returns True/False

# CORRECT approach for lock acquisition:
acquired = r.set("lock:resource", "owner_id", nx=True, ex=30)
# This is ONE atomic command: SET key value NX EX 30
```

### 1.8 INCR / DECR / INCRBY / DECRBY / INCRBYFLOAT

```python
# Start with a counter
r.set("page:views:/home", "0")

# INCR — increment by 1
r.incr("page:views:/home")  # 1
r.incr("page:views:/home")  # 2

# DECR — decrement by 1
r.decr("page:views:/home")  # 1

# INCRBY — increment by specific integer
r.incrby("page:views:/home", 10)  # 11

# DECRBY — decrement by specific integer
r.decrby("page:views:/home", 5)   # 6

# INCRBYFLOAT — increment by float (for monetary/precision ops)
r.set("wallet:user:1001", "100.00")
r.incrbyfloat("wallet:user:1001", 25.50)   # "125.5"
r.incrbyfloat("wallet:user:1001", -10.25)  # "115.25"

# Key insight: INCR on a non-existent key starts from 0
r.delete("counter:new")
r.incr("counter:new")  # Returns 1 (treats missing key as 0)
```

**Time Complexity**: All O(1) — single-threaded event loop guarantees atomicity without locks.

---

## 2. Hashes

Hashes are maps of field-value pairs under a single key. Think of them as a Python dict stored in Redis. Ideal for objects/entities.

Internally:
- **listpack** (formerly ziplist) — when ≤ 128 fields AND all values ≤ 64 bytes (configurable)
- **hashtable** — otherwise (O(1) per field access)

### 2.1 HSET — Set Fields

```python
# HSET — set one or more fields
r.hset("user:1001", "name", "Alice")

# Multiple fields at once (Redis 4.0+)
r.hset("user:1001", mapping={
    "name": "Alice",
    "email": "alice@example.com",
    "age": "30",
    "city": "Mumbai",
    "plan": "premium"
})

# Returns number of NEW fields added (not updated ones)
```

**Time Complexity**: O(1) per field, O(N) for multiple fields

### 2.2 HGET / HMGET / HGETALL

```python
# HGET — get single field
name = r.hget("user:1001", "name")  # "Alice"
missing = r.hget("user:1001", "nonexistent")  # None

# HMGET — get multiple fields in one call
values = r.hmget("user:1001", "name", "email", "plan")
# ["Alice", "alice@example.com", "premium"]

# HGETALL — get ALL fields and values
user = r.hgetall("user:1001")
# {"name": "Alice", "email": "alice@example.com", "age": "30", ...}
```

**WARNING**: `HGETALL` on a hash with 10,000 fields blocks Redis for the duration. Use `HSCAN` for large hashes.

### 2.3 HDEL / HEXISTS / HLEN

```python
# HDEL — delete one or more fields
r.hdel("user:1001", "city")           # Delete one field
r.hdel("user:1001", "city", "plan")   # Delete multiple fields
# Returns number of fields actually removed

# HEXISTS — check if field exists (without fetching value)
exists = r.hexists("user:1001", "email")  # True/False

# HLEN — count fields in hash
field_count = r.hlen("user:1001")  # 4
```

### 2.4 HINCRBY / HINCRBYFLOAT — Atomic Field Counters

```python
# HINCRBY — atomically increment integer field
r.hset("product:5001", mapping={"views": "0", "stock": "100"})
r.hincrby("product:5001", "views", 1)    # 1
r.hincrby("product:5001", "stock", -1)   # 99 (decrement by negative)

# HINCRBYFLOAT — increment float field
r.hset("cart:user:1001", "total", "0.00")
r.hincrbyfloat("cart:user:1001", "total", 29.99)   # "29.99"
r.hincrbyfloat("cart:user:1001", "total", 15.50)   # "45.49"

# Key insight: HINCRBY is atomic — perfect for stock/inventory
# 1000 concurrent requests decrementing stock will never oversell
```

### 2.5 HKEYS / HVALS / HSETNX

```python
# HKEYS — get all field names (without values)
fields = r.hkeys("user:1001")  # ["name", "email", "age", ...]

# HVALS — get all values (without field names)
values = r.hvals("user:1001")  # ["Alice", "alice@example.com", "30", ...]

# HSETNX — set field ONLY if it doesn't exist
# Use case: set default value without overwriting user changes
r.hsetnx("user:1001", "plan", "free")  # Only sets if "plan" field missing
```

### 2.6 HSCAN — Iterate Large Hashes Safely

```python
# HSCAN — cursor-based iteration (non-blocking)
cursor = 0
all_fields = {}
while True:
    cursor, data = r.hscan("user:1001", cursor=cursor, count=100)
    all_fields.update(data)
    if cursor == 0:
        break

# With pattern matching
cursor = 0
while True:
    cursor, data = r.hscan("config:app", cursor=cursor, match="feature_*")
    for field, value in data.items():
        print(f"{field} = {value}")
    if cursor == 0:
        break
```

**Time Complexity**: O(1) per iteration (processes ~count elements)

### 2.7 Real-World Pattern — User Profile with Hash

```python
class UserProfile:
    def __init__(self, redis_client):
        self.r = redis_client
    
    def create_user(self, user_id: str, data: dict):
        key = f"user:{user_id}"
        # Store all fields atomically
        self.r.hset(key, mapping=data)
        # Set expiry on the entire hash
        self.r.expire(key, 86400 * 30)  # 30 days
    
    def get_user(self, user_id: str) -> dict:
        return self.r.hgetall(f"user:{user_id}")
    
    def update_field(self, user_id: str, field: str, value: str):
        self.r.hset(f"user:{user_id}", field, value)
    
    def increment_login_count(self, user_id: str):
        return self.r.hincrby(f"user:{user_id}", "login_count", 1)
    
    def delete_user(self, user_id: str):
        self.r.delete(f"user:{user_id}")

# Usage
profile = UserProfile(r)
profile.create_user("1001", {
    "name": "Alice",
    "email": "alice@example.com",
    "login_count": "0",
    "created_at": "2026-01-15T10:00:00Z"
})
profile.increment_login_count("1001")
```

---

## 3. Lists

Redis Lists are doubly-linked lists of strings. They support push/pop from both ends in O(1). Ideal for queues, activity feeds, and recent-items lists.

Internal encoding:
- **listpack** — when ≤ 128 elements AND all elements ≤ 64 bytes
- **quicklist** — otherwise (a linked list of listpacks for memory efficiency)

### 3.1 LPUSH / RPUSH — Add Elements

```python
# LPUSH — push to the LEFT (head/front)
r.lpush("queue:emails", "email_001")  # [email_001]
r.lpush("queue:emails", "email_002")  # [email_002, email_001]

# Push multiple values at once (added left to right)
r.lpush("queue:emails", "email_003", "email_004")
# [email_004, email_003, email_002, email_001]

# RPUSH — push to the RIGHT (tail/end)
r.rpush("timeline:user:1001", "post_001")  # [post_001]
r.rpush("timeline:user:1001", "post_002")  # [post_001, post_002]

# LPUSHX / RPUSHX — push ONLY if list already exists
r.lpushx("queue:emails", "email_005")      # Works (list exists)
r.lpushx("queue:nonexistent", "email_006")  # Does nothing (returns 0)
```

**Time Complexity**: O(1) for single element, O(N) for N elements

### 3.2 LPOP / RPOP — Remove and Return

```python
# LPOP — pop from LEFT (head)
item = r.lpop("queue:emails")  # Returns "email_004", removes it

# RPOP — pop from RIGHT (tail)
item = r.rpop("queue:emails")  # Returns "email_001", removes it

# Pop multiple elements (Redis 6.2+)
items = r.lpop("queue:emails", 3)  # Returns list of up to 3 items

# RPOPLPUSH (deprecated) → LMOVE
# Atomically pop from one list, push to another
# Use case: reliable queue with processing list
r.rpush("queue:pending", "job_001", "job_002", "job_003")
job = r.lmove("queue:pending", "queue:processing", "LEFT", "RIGHT")
# Pops from left of pending, pushes to right of processing
```

### 3.3 BLPOP / BRPOP — Blocking Pop (Queue Consumer)

```python
# BLPOP — blocking left pop (waits until element available or timeout)
# timeout=0 means block forever
result = r.blpop("queue:tasks", timeout=30)
# Returns ("queue:tasks", "task_data") or None on timeout

# Can wait on multiple queues (priority queue pattern)
result = r.blpop(["queue:high", "queue:medium", "queue:low"], timeout=10)
# Returns from first non-empty queue in order

# BRPOP — same but from the right
result = r.brpop("queue:tasks", timeout=5)
```

**Key Insight**: BLPOP is the foundation of Redis-as-queue. A worker calls BLPOP in a loop — it sleeps efficiently (no polling) until work arrives.

### 3.4 LRANGE — Read Sublist (Without Removing)

```python
# LRANGE — get elements by index range (0-based, inclusive)
r.rpush("recent:posts", "p1", "p2", "p3", "p4", "p5")

first_three = r.lrange("recent:posts", 0, 2)    # ["p1", "p2", "p3"]
last_two = r.lrange("recent:posts", -2, -1)      # ["p4", "p5"]
all_items = r.lrange("recent:posts", 0, -1)      # ["p1","p2","p3","p4","p5"]

# Paginated feed pattern
page_size = 10
page_num = 2  # 0-indexed
start = page_num * page_size
end = start + page_size - 1
feed_page = r.lrange("feed:user:1001", start, end)
```

**Time Complexity**: O(S+N) where S = offset from head, N = number of elements returned

### 3.5 LINDEX / LLEN / LSET

```python
# LINDEX — get element at index (O(N) for middle elements!)
r.rpush("mylist", "a", "b", "c", "d", "e")
element = r.lindex("mylist", 0)    # "a" (head — O(1))
element = r.lindex("mylist", -1)   # "e" (tail — O(1))
element = r.lindex("mylist", 2)    # "c" (middle — O(N))

# LLEN — get list length
length = r.llen("mylist")  # 5, always O(1)

# LSET — set element at index (overwrites)
r.lset("mylist", 2, "C_UPDATED")
# ["a", "b", "C_UPDATED", "d", "e"]
```

### 3.6 LREM — Remove by Value

```python
# LREM count value
# count > 0: remove 'count' occurrences from HEAD to TAIL
# count < 0: remove 'count' occurrences from TAIL to HEAD
# count = 0: remove ALL occurrences

r.rpush("items", "a", "b", "a", "c", "a", "d")
r.lrem("items", 2, "a")   # Remove first 2 "a" from head → ["b", "c", "a", "d"]
r.lrem("items", -1, "a")  # Remove last 1 "a" from tail → ["b", "c", "d"]
r.lrem("items", 0, "c")   # Remove all "c" → ["b", "d"]
```

### 3.7 LINSERT — Insert Before/After a Pivot

```python
r.rpush("tasks", "task_1", "task_3", "task_5")

# Insert BEFORE a pivot element
r.linsert("tasks", "BEFORE", "task_3", "task_2")
# ["task_1", "task_2", "task_3", "task_5"]

# Insert AFTER a pivot element
r.linsert("tasks", "AFTER", "task_3", "task_4")
# ["task_1", "task_2", "task_3", "task_4", "task_5"]
```

**Time Complexity**: O(N) — must scan to find pivot

### 3.8 LTRIM — Trim List to Range (Capped List)

```python
# Keep only the most recent 100 notifications
r.lpush("notifications:user:1001", "new_notification_json")
r.ltrim("notifications:user:1001", 0, 99)
# List never exceeds 100 elements

# Pattern: bounded activity feed
def add_to_feed(user_id: str, activity: str, max_size: int = 1000):
    key = f"feed:{user_id}"
    pipe = r.pipeline()
    pipe.lpush(key, activity)
    pipe.ltrim(key, 0, max_size - 1)
    pipe.execute()
```

---

## 4. Sets

Redis Sets are unordered collections of unique strings. They support membership tests in O(1) and powerful set operations (union, intersection, difference).

Internal encoding:
- **listpack** — when ≤ 128 elements AND all elements ≤ 64 bytes
- **hashtable** — otherwise

### 4.1 SADD / SREM — Add and Remove Members

```python
# SADD — add one or more members
r.sadd("tags:post:001", "python", "redis", "backend")
# Returns number of NEW members added (not already present)

added = r.sadd("tags:post:001", "redis", "database")
# Returns 1 (only "database" is new, "redis" already existed)

# SREM — remove one or more members
removed = r.srem("tags:post:001", "backend", "nonexistent")
# Returns 1 (only "backend" was actually present)
```

### 4.2 SISMEMBER / SMISMEMBER — Membership Tests

```python
# SISMEMBER — check if member exists
is_tagged = r.sismember("tags:post:001", "python")  # True
is_tagged = r.sismember("tags:post:001", "java")    # False

# SMISMEMBER — check multiple members at once (Redis 6.2+)
results = r.smismember("tags:post:001", "python", "java", "redis")
# [True, False, True]

# Use case: check if user has specific permission
has_admin = r.sismember(f"roles:user:1001", "admin")
```

**Time Complexity**: O(1) per member — this is why Sets excel at lookups

### 4.3 SMEMBERS / SCARD / SRANDMEMBER / SPOP

```python
# SMEMBERS — get ALL members
all_tags = r.smembers("tags:post:001")
# {"python", "redis", "database"}

# SCARD — get cardinality (count) — always O(1)
count = r.scard("tags:post:001")  # 3

# SRANDMEMBER — get random member(s) WITHOUT removing
random_tag = r.srandmember("tags:post:001")       # One random member
random_tags = r.srandmember("tags:post:001", 2)   # Two random members

# SPOP — get and REMOVE random member(s)
popped = r.spop("tags:post:001")      # Removes and returns one random member
popped = r.spop("tags:post:001", 2)   # Removes and returns two random
```

### 4.4 Set Operations — SUNION / SINTER / SDIFF

```python
# Setup
r.sadd("user:1001:skills", "python", "redis", "postgres", "docker")
r.sadd("user:1002:skills", "python", "mongodb", "docker", "kubernetes")
r.sadd("user:1003:skills", "python", "redis", "kafka", "docker")

# SUNION — all unique skills across all users
all_skills = r.sunion("user:1001:skills", "user:1002:skills", "user:1003:skills")
# {"python", "redis", "postgres", "docker", "mongodb", "kubernetes", "kafka"}

# SINTER — skills common to ALL users
common = r.sinter("user:1001:skills", "user:1002:skills", "user:1003:skills")
# {"python", "docker"}

# SDIFF — skills in first set but NOT in second
unique_to_1001 = r.sdiff("user:1001:skills", "user:1002:skills")
# {"redis", "postgres"} — skills 1001 has that 1002 doesn't

# Store results in a new key
r.sunionstore("all:skills", "user:1001:skills", "user:1002:skills")
r.sinterstore("common:skills", "user:1001:skills", "user:1002:skills")
r.sdiffstore("unique:1001", "user:1001:skills", "user:1002:skills")
```

**Use Cases**:
- `SINTER` → mutual friends, common tags, shared interests
- `SDIFF` → recommendation: "skills others have that you don't"
- `SUNION` → all unique visitors across pages

### 4.5 SSCAN — Iterate Large Sets Safely

```python
cursor = 0
members = set()
while True:
    cursor, batch = r.sscan("large:set", cursor=cursor, count=200)
    members.update(batch)
    if cursor == 0:
        break
```

### 4.6 Real-World Pattern — Online Users / Unique Visitors

```python
import time
from datetime import date

class UniqueVisitorTracker:
    def __init__(self, redis_client):
        self.r = redis_client
    
    def track_visit(self, page: str, user_id: str):
        today = date.today().isoformat()
        key = f"visitors:{page}:{today}"
        self.r.sadd(key, user_id)
        self.r.expire(key, 86400 * 7)  # Keep 7 days
    
    def get_unique_count(self, page: str, day: str) -> int:
        return self.r.scard(f"visitors:{page}:{day}")
    
    def get_visitors_across_days(self, page: str, days: list) -> set:
        keys = [f"visitors:{page}:{d}" for d in days]
        return self.r.sunion(*keys)
    
    def get_returning_visitors(self, page: str, day1: str, day2: str) -> set:
        return self.r.sinter(f"visitors:{page}:{day1}", f"visitors:{page}:{day2}")

tracker = UniqueVisitorTracker(r)
tracker.track_visit("/home", "user_1001")
tracker.track_visit("/home", "user_1002")
tracker.track_visit("/home", "user_1001")  # Duplicate — ignored
print(tracker.get_unique_count("/home", "2026-01-15"))  # 2
```

---

## 5. Sorted Sets (ZSets)

Sorted Sets combine Set uniqueness with a floating-point score per member. Members are always ordered by score. This is Redis's most powerful data structure — the backbone of leaderboards, priority queues, time-series indexes, and range queries.

Internal encoding:
- **listpack** — when ≤ 128 members AND all members ≤ 64 bytes
- **skiplist + hashtable** — otherwise (O(log N) inserts, O(1) score lookups)

### 5.1 ZADD — Add Members with Scores

```python
# ZADD — add members with scores
r.zadd("leaderboard:game1", {"alice": 1500, "bob": 1350, "charlie": 1800})

# Add/update single member
r.zadd("leaderboard:game1", {"dave": 1200})

# Flags:
# NX — only add NEW members (don't update existing)
r.zadd("leaderboard:game1", {"alice": 9999}, nx=True)  # Ignored, alice exists

# XX — only UPDATE existing (don't add new)
r.zadd("leaderboard:game1", {"newplayer": 500}, xx=True)  # Ignored, doesn't exist

# GT — only update if new score > current score
r.zadd("leaderboard:game1", {"alice": 1600}, gt=True)  # Updated (1600 > 1500)
r.zadd("leaderboard:game1", {"alice": 1400}, gt=True)  # Ignored (1400 < 1600)

# LT — only update if new score < current score (useful for "best time" boards)
r.zadd("speedrun:level1", {"alice": 45.2}, lt=True)  # Only keeps lower time

# CH — return count of CHANGED members (added + updated), not just added
changed = r.zadd("leaderboard:game1", {"alice": 1700}, ch=True)
```

**Time Complexity**: O(log N) per member

### 5.2 ZSCORE / ZRANK / ZREVRANK

```python
# ZSCORE — get score of a specific member
score = r.zscore("leaderboard:game1", "charlie")  # 1800.0

# ZRANK — get 0-based rank (lowest score = rank 0)
rank = r.zrank("leaderboard:game1", "charlie")   # 3 (highest score = last)

# ZREVRANK — get 0-based rank in DESCENDING order (highest score = rank 0)
rank = r.zrevrank("leaderboard:game1", "charlie")  # 0 (top of leaderboard)

# Use case: "You are ranked #X"
def get_player_rank(player: str) -> int:
    rank = r.zrevrank("leaderboard:game1", player)
    return rank + 1 if rank is not None else None  # Convert 0-based to 1-based
```

### 5.3 ZRANGE / ZREVRANGE — Range by Rank

```python
# ZRANGE — get members by rank range (ascending score)
# Top 3 players (by score descending):
top_3 = r.zrevrange("leaderboard:game1", 0, 2)
# ["charlie", "alice", "bob"]

# With scores:
top_3_with_scores = r.zrevrange("leaderboard:game1", 0, 2, withscores=True)
# [("charlie", 1800.0), ("alice", 1700.0), ("bob", 1350.0)]

# Bottom 5 (lowest scores):
bottom_5 = r.zrange("leaderboard:game1", 0, 4, withscores=True)

# All members:
all_members = r.zrange("leaderboard:game1", 0, -1, withscores=True)

# Redis 6.2+ ZRANGE with REV and BYSCORE:
# Replaces ZRANGEBYSCORE, ZREVRANGEBYSCORE
top_by_score = r.zrange("leaderboard:game1", 1500, 2000, byscore=True, withscores=True)
```

**Time Complexity**: O(log N + M) where M = number of elements returned

### 5.4 ZRANGEBYSCORE — Range by Score Value

```python
# Get all players with score between 1300 and 1600
mid_tier = r.zrangebyscore("leaderboard:game1", 1300, 1600, withscores=True)
# [("bob", 1350.0), ("alice", 1600.0)]

# Exclusive bounds with "("
# Score > 1300 and < 1600 (exclusive both sides)
result = r.zrangebyscore("leaderboard:game1", "(1300", "(1600")

# Infinite bounds
all_above_1500 = r.zrangebyscore("leaderboard:game1", 1500, "+inf")
all_below_1500 = r.zrangebyscore("leaderboard:game1", "-inf", 1500)

# With LIMIT (pagination)
# Skip first 10, return next 5
page = r.zrangebyscore("leaderboard:game1", "-inf", "+inf",
                        start=10, num=5, withscores=True)

# Time-based queries (using Unix timestamps as scores)
now = time.time()
one_hour_ago = now - 3600
recent_events = r.zrangebyscore("events:timeline", one_hour_ago, now)
```

### 5.5 ZREM / ZREMRANGEBYSCORE / ZREMRANGEBYRANK

```python
# ZREM — remove specific members
removed = r.zrem("leaderboard:game1", "dave", "nonexistent")
# Returns count of actually removed members

# ZREMRANGEBYSCORE — remove all members within score range
# Use case: expire old events from a time-based sorted set
cutoff = time.time() - 86400  # 24 hours ago
removed_count = r.zremrangebyscore("events:timeline", "-inf", cutoff)

# ZREMRANGEBYRANK — remove by rank range
# Keep only top 100, remove the rest
r.zremrangebyrank("leaderboard:game1", 0, -101)
# Removes everyone except top 100
```

### 5.6 ZINCRBY — Atomic Score Increment

```python
# ZINCRBY — increment a member's score atomically
new_score = r.zincrby("leaderboard:game1", 50, "alice")
# Alice's score += 50, returns new score

# Decrement by using negative value
new_score = r.zincrby("leaderboard:game1", -20, "alice")

# Use case: real-time vote counting
def upvote_post(post_id: str):
    return r.zincrby("trending:posts", 1, post_id)

def downvote_post(post_id: str):
    return r.zincrby("trending:posts", -1, post_id)
```

### 5.7 ZCARD / ZCOUNT

```python
# ZCARD — total member count
total_players = r.zcard("leaderboard:game1")  # O(1)

# ZCOUNT — count members within score range
high_scorers = r.zcount("leaderboard:game1", 1500, "+inf")
# How many players have score >= 1500?
```

### 5.8 Set Operations on Sorted Sets

```python
# ZUNIONSTORE — union of multiple sorted sets into destination
r.zadd("scores:week1", {"alice": 100, "bob": 80})
r.zadd("scores:week2", {"alice": 90, "bob": 120, "charlie": 70})

# Sum scores across weeks
r.zunionstore("scores:total", ["scores:week1", "scores:week2"], aggregate="SUM")
# alice=190, bob=200, charlie=70

# Or take MAX
r.zunionstore("scores:best", ["scores:week1", "scores:week2"], aggregate="MAX")
# alice=100, bob=120, charlie=70

# ZINTERSTORE — intersection (only members in ALL sets)
r.zinterstore("scores:both_weeks", ["scores:week1", "scores:week2"], aggregate="SUM")
# alice=190, bob=200 (charlie excluded — not in week1)

# Weighted union (week2 counts double)
r.zunionstore("scores:weighted", 
              {"scores:week1": 1, "scores:week2": 2},
              aggregate="SUM")
# alice=100+180=280, bob=80+240=320, charlie=140
```

### 5.9 ZSCAN — Safe Iteration

```python
cursor = 0
while True:
    cursor, members = r.zscan("leaderboard:game1", cursor=cursor, count=100)
    for member, score in members:
        print(f"{member}: {score}")
    if cursor == 0:
        break
```

### 5.10 Real-World Pattern — Sliding Window Rate Limiter

```python
def is_allowed(user_id: str, max_requests: int, window_seconds: int) -> bool:
    key = f"ratelimit:{user_id}"
    now = time.time()
    window_start = now - window_seconds
    
    pipe = r.pipeline()
    # Remove entries outside the window
    pipe.zremrangebyscore(key, "-inf", window_start)
    # Count entries in current window
    pipe.zcard(key)
    # Add current request
    pipe.zadd(key, {f"{now}:{id(now)}": now})
    # Set expiry on the key itself
    pipe.expire(key, window_seconds)
    
    results = pipe.execute()
    current_count = results[1]
    
    return current_count < max_requests
```

---

## 6. Bitmaps

Bitmaps are not a separate data type — they're operations on String values that treat them as bit arrays. Each bit is addressable individually. A string of 1 MB = 8,388,608 individually addressable bits.

### 6.1 SETBIT / GETBIT

```python
# SETBIT — set a specific bit to 0 or 1
# Use case: track daily active users (DAU)
# Bit offset = user_id, value = 1 means "active today"
r.setbit("dau:2026-01-15", 1001, 1)  # User 1001 active
r.setbit("dau:2026-01-15", 1002, 1)  # User 1002 active
r.setbit("dau:2026-01-15", 1003, 1)  # User 1003 active

# GETBIT — check if a specific bit is set
is_active = r.getbit("dau:2026-01-15", 1001)  # 1
is_active = r.getbit("dau:2026-01-15", 9999)  # 0 (unset bits default to 0)
```

**Memory**: 1 million users = 125 KB per day. Compare to storing 1M keys.

### 6.2 BITCOUNT — Count Set Bits

```python
# BITCOUNT — count bits set to 1
dau_count = r.bitcount("dau:2026-01-15")  # Number of active users today

# Count bits in byte range [start, end]
partial = r.bitcount("dau:2026-01-15", 0, 100)  # Bits in first 101 bytes
```

### 6.3 BITOP — Bitwise Operations Between Keys

```python
# BITOP AND — users active on BOTH days (retention)
r.bitop("AND", "active:both_days", "dau:2026-01-15", "dau:2026-01-16")
retention_count = r.bitcount("active:both_days")

# BITOP OR — users active on EITHER day (reach)
r.bitop("OR", "active:either_day", "dau:2026-01-15", "dau:2026-01-16")
reach_count = r.bitcount("active:either_day")

# BITOP XOR — users active on exactly one day
r.bitop("XOR", "active:one_day_only", "dau:2026-01-15", "dau:2026-01-16")

# BITOP NOT — invert bits (users NOT active)
r.bitop("NOT", "inactive:2026-01-15", "dau:2026-01-15")
```

### 6.4 BITPOS — Find First Bit

```python
# Find first bit set to 1 (first active user)
first_active = r.bitpos("dau:2026-01-15", 1)  # Returns bit offset

# Find first bit set to 0 (first inactive user ID slot)
first_inactive = r.bitpos("dau:2026-01-15", 0)
```

### 6.5 BITFIELD — Multi-Bit Counter Arrays

```python
# BITFIELD — treat a string as an array of arbitrary-width integers
# Store multiple counters in a single key

# Create an array of 8-bit unsigned counters (0-255 each)
# Counter at offset 0: page views for section A
# Counter at offset 8: page views for section B
r.bitfield("counters:page", "SET", "u8", 0, 0)    # Initialize counter A
r.bitfield("counters:page", "SET", "u8", 8, 0)    # Initialize counter B

# Increment counter A by 1
r.bitfield("counters:page", "INCRBY", "u8", 0, 1)

# Get counter A value
result = r.bitfield("counters:page", "GET", "u8", 0)
# [current_value]

# Overflow handling
r.bitfield("counters:page", "OVERFLOW", "SAT", "INCRBY", "u8", 0, 1)
# SAT = saturate at 255 (won't wrap around)
# WRAP = wrap around (default)
# FAIL = return None if overflow would occur
```

---

## 7. HyperLogLog

HyperLogLog (HLL) is a probabilistic data structure for cardinality estimation (counting unique elements). It uses only ~12 KB regardless of the number of unique elements, with a standard error of 0.81%.

### 7.1 PFADD / PFCOUNT / PFMERGE

```python
# PFADD — add elements to HLL
r.pfadd("unique:visitors:2026-01-15", "user_1001", "user_1002", "user_1003")
r.pfadd("unique:visitors:2026-01-15", "user_1001")  # Duplicate — cardinality unchanged

# PFCOUNT — estimate cardinality
unique_count = r.pfcount("unique:visitors:2026-01-15")
# ~3 (with 0.81% standard error for large sets)

# Add millions of elements — still 12 KB
for i in range(1_000_000):
    r.pfadd("unique:visitors:2026-01-15", f"user_{i}")
count = r.pfcount("unique:visitors:2026-01-15")
# ~1,000,000 ± 8,100

# PFMERGE — merge multiple HLLs (union of unique elements)
r.pfadd("unique:page:/home:2026-01-15", "u1", "u2", "u3")
r.pfadd("unique:page:/home:2026-01-16", "u2", "u3", "u4", "u5")
r.pfmerge("unique:page:/home:week", 
          "unique:page:/home:2026-01-15", 
          "unique:page:/home:2026-01-16")
weekly_unique = r.pfcount("unique:page:/home:week")  # ~5
```

**When to use HLL vs Set**:
- Set: exact count needed, < 100K members, need to list/test members
- HLL: approximate count OK, millions+ unique elements, memory constrained

---

## 8. Streams

Redis Streams are append-only log structures with consumer groups — essentially a built-in message queue with persistence, consumer acknowledgment, and replayability.

### 8.1 XADD — Append Messages

```python
# XADD — add entry to stream (returns generated ID)
entry_id = r.xadd("events:orders", {
    "order_id": "ORD-5001",
    "user_id": "1001",
    "amount": "99.99",
    "status": "created"
})
# Returns something like "1705312800000-0" (timestamp-sequence)

# With explicit ID (rarely needed)
r.xadd("events:orders", {"data": "value"}, id="1705312800000-5")

# With MAXLEN — cap stream size
r.xadd("events:orders", {"data": "value"}, maxlen=10000)

# With approximate MAXLEN (~) — more efficient, allows slight overshoot
r.xadd("events:orders", {"data": "value"}, maxlen=10000, approximate=True)

# With MINID — trim entries older than ID
r.xadd("events:orders", {"data": "value"}, minid="1705312800000-0")
```

### 8.2 XREAD — Read Messages (Fan-out)

```python
# XREAD — read new entries from one or more streams
# Read entries after a specific ID (for catch-up)
entries = r.xread({"events:orders": "0-0"}, count=10)
# Returns: [["events:orders", [("id1", {fields}), ("id2", {fields})]]]

# Block until new entries arrive (like BLPOP for streams)
entries = r.xread({"events:orders": "$"}, count=1, block=5000)
# "$" means "only new entries from now"
# block=5000 means wait up to 5 seconds

# Read from multiple streams simultaneously
entries = r.xread({
    "events:orders": "$",
    "events:payments": "$"
}, count=10, block=10000)
```

### 8.3 Consumer Groups — Reliable Message Processing

```python
# Create consumer group (starting from beginning of stream)
try:
    r.xgroup_create("events:orders", "order-processors", id="0", mkstream=True)
except redis.ResponseError:
    pass  # Group already exists

# XREADGROUP — read as part of a consumer group
# Each message delivered to exactly one consumer in the group
entries = r.xreadgroup(
    groupname="order-processors",
    consumername="worker-1",
    streams={"events:orders": ">"},  # ">" means undelivered messages only
    count=10,
    block=5000
)

# XACK — acknowledge message processing
if entries:
    for stream, messages in entries:
        for msg_id, fields in messages:
            process_order(fields)
            r.xack("events:orders", "order-processors", msg_id)

# XPENDING — check unacknowledged messages
pending = r.xpending("events:orders", "order-processors")
# Shows: total pending, min ID, max ID, consumers with pending counts

# XCLAIM — steal stale messages from dead consumers
# If worker-1 crashed, worker-2 claims its messages after 60 seconds
stale_messages = r.xclaim(
    "events:orders", "order-processors", "worker-2",
    min_idle_time=60000,  # 60 seconds idle
    message_ids=["1705312800000-0", "1705312800001-0"]
)
```

### 8.4 XLEN / XRANGE / XINFO

```python
# XLEN — stream length
length = r.xlen("events:orders")

# XRANGE — read range by ID
# All entries between two timestamps
entries = r.xrange("events:orders", min="-", max="+", count=100)
# Between specific IDs
entries = r.xrange("events:orders", "1705312800000-0", "1705312900000-0")

# XREVRANGE — same but in reverse order
latest = r.xrevrange("events:orders", "+", "-", count=5)

# XINFO — stream metadata
info = r.xinfo_stream("events:orders")
groups = r.xinfo_groups("events:orders")
consumers = r.xinfo_consumers("events:orders", "order-processors")
```

### 8.5 Stream Consumer Pattern

```python
import signal
import sys

class StreamConsumer:
    def __init__(self, redis_client, stream: str, group: str, consumer: str):
        self.r = redis_client
        self.stream = stream
        self.group = group
        self.consumer = consumer
        self.running = True
        signal.signal(signal.SIGTERM, self._shutdown)
    
    def _shutdown(self, *args):
        self.running = False
    
    def _ensure_group(self):
        try:
            self.r.xgroup_create(self.stream, self.group, id="0", mkstream=True)
        except redis.ResponseError:
            pass
    
    def process_message(self, msg_id: str, fields: dict):
        raise NotImplementedError
    
    def run(self):
        self._ensure_group()
        
        # First: process any previously read but unacknowledged messages
        pending = self.r.xreadgroup(
            self.group, self.consumer,
            streams={self.stream: "0"},  # "0" = pending messages for this consumer
            count=10
        )
        if pending:
            for stream, messages in pending:
                for msg_id, fields in messages:
                    self.process_message(msg_id, fields)
                    self.r.xack(self.stream, self.group, msg_id)
        
        # Then: consume new messages
        while self.running:
            entries = self.r.xreadgroup(
                self.group, self.consumer,
                streams={self.stream: ">"},
                count=10, block=2000
            )
            if not entries:
                continue
            for stream, messages in entries:
                for msg_id, fields in messages:
                    try:
                        self.process_message(msg_id, fields)
                        self.r.xack(self.stream, self.group, msg_id)
                    except Exception as e:
                        print(f"Error processing {msg_id}: {e}")
                        # Message stays pending — will be retried or claimed
```

---

## 9. Keys & Expiry Management

### 9.1 Key Operations

```python
# EXISTS — check if key exists
exists = r.exists("user:1001")  # Returns count of existing keys
exists = r.exists("key1", "key2", "key3")  # Count of how many exist

# DEL — delete keys (blocking)
deleted = r.delete("user:1001", "user:1002")  # Returns count deleted

# UNLINK — delete keys (non-blocking, async actual memory free)
r.unlink("large:hash:key")  # Preferred for large keys (millions of fields)

# TYPE — get data type of a key
key_type = r.type("user:1001")  # "string", "hash", "list", "set", "zset", "stream"

# RENAME — rename a key
r.rename("old:key", "new:key")       # Overwrites destination if exists
r.renamenx("old:key", "new:key")     # Only rename if destination doesn't exist

# KEYS — find keys matching pattern (DANGEROUS in production!)
# Blocks Redis while scanning ALL keys
keys = r.keys("user:*")  # NEVER use in production — use SCAN instead

# SCAN — safe cursor-based key iteration
cursor = 0
user_keys = []
while True:
    cursor, keys = r.scan(cursor=cursor, match="user:*", count=100)
    user_keys.extend(keys)
    if cursor == 0:
        break

# RANDOMKEY — get a random key
random = r.randomkey()

# DUMP / RESTORE — serialize/deserialize a key (for migration)
serialized = r.dump("user:1001")
# r.restore("user:1001:copy", 0, serialized)  # TTL=0 means no expiry
```

### 9.2 Expiry Operations

```python
# EXPIRE — set TTL in seconds
r.set("session:abc", "data")
r.expire("session:abc", 3600)  # Expires in 1 hour

# PEXPIRE — set TTL in milliseconds
r.pexpire("session:abc", 3600000)

# EXPIREAT — expire at absolute Unix timestamp
r.expireat("session:abc", int(time.time()) + 3600)

# PEXPIREAT — expire at absolute timestamp in milliseconds
r.pexpireat("session:abc", int(time.time() * 1000) + 3600000)

# TTL — check remaining time to live (seconds)
remaining = r.ttl("session:abc")
# Returns: seconds remaining, -1 (no expiry), -2 (key doesn't exist)

# PTTL — remaining TTL in milliseconds
remaining_ms = r.pttl("session:abc")

# PERSIST — remove expiry (make key permanent)
r.persist("session:abc")

# EXPIRETIME — get absolute Unix timestamp when key expires (Redis 7.0+)
expires_at = r.expiretime("session:abc")
```

**Key behavior**: When a key expires, it's lazily deleted on access OR actively deleted by Redis's periodic cleanup (10 times/second by default). Memory is freed immediately.

### 9.3 Key Space Notifications

```python
# Enable keyspace notifications (redis.conf: notify-keyspace-events Ex)
# Subscribe to expiry events
pubsub = r.pubsub()
pubsub.psubscribe("__keyevent@0__:expired")

for message in pubsub.listen():
    if message["type"] == "pmessage":
        expired_key = message["data"]
        print(f"Key expired: {expired_key}")
        # Use case: session cleanup, delayed job execution
```

---

## 10. Transactions & Pipelines

### 10.1 Pipeline — Batch Commands (No Atomicity)

```python
# Pipeline batches commands into a single round trip
# Commands are NOT atomic — other clients can interleave
pipe = r.pipeline(transaction=False)
pipe.set("key1", "val1")
pipe.set("key2", "val2")
pipe.get("key1")
pipe.incr("counter")
results = pipe.execute()
# [True, True, "val1", 1]

# Performance: 100 individual commands = 100 round trips (~50ms)
#              100 pipelined commands = 1 round trip (~0.5ms)
```

### 10.2 MULTI/EXEC — Atomic Transactions

```python
# Transaction: all commands execute atomically (no interleaving)
pipe = r.pipeline(transaction=True)  # This is the default
pipe.multi()
pipe.decrby("account:A:balance", 100)
pipe.incrby("account:B:balance", 100)
results = pipe.execute()
# Both succeed or both fail (but no rollback on command errors!)
```

**Critical distinction**: Redis transactions are NOT like SQL transactions.
- They guarantee atomic execution (no interleaving).
- They do NOT guarantee rollback — if one command errors, others still execute.
- They do NOT support conditional logic within the transaction.

### 10.3 WATCH — Optimistic Locking (CAS)

```python
# WATCH + MULTI/EXEC = Compare-And-Swap
# Use case: atomic balance check + deduction

def transfer_funds(from_account: str, to_account: str, amount: int) -> bool:
    with r.pipeline() as pipe:
        while True:
            try:
                # Watch the source account
                pipe.watch(f"account:{from_account}:balance")
                
                # Check balance (outside transaction)
                balance = int(pipe.get(f"account:{from_account}:balance") or 0)
                if balance < amount:
                    pipe.unwatch()
                    return False  # Insufficient funds
                
                # Start transaction
                pipe.multi()
                pipe.decrby(f"account:{from_account}:balance", amount)
                pipe.incrby(f"account:{to_account}:balance", amount)
                pipe.execute()  # Succeeds only if watched key unchanged
                return True
                
            except redis.WatchError:
                # Another client modified the balance — retry
                continue

# If between WATCH and EXEC another client changes the watched key,
# EXEC returns None (transaction aborted). We retry.
```

---

## 11. Atomic Increment Operations

### 11.1 Why Redis Counters are Atomic

Redis is single-threaded (one command at a time on the event loop). `INCR` is a single command → always atomic. No locks needed. No race conditions. Even with 10,000 concurrent clients, every INCR is sequential.

```
Client A: INCR counter → Redis processes → returns 1
Client B: INCR counter → Redis processes → returns 2
Client C: INCR counter → Redis processes → returns 3
```

Compare with non-atomic read-modify-write:
```
Client A: GET counter → 0
Client B: GET counter → 0    ← RACE CONDITION
Client A: SET counter 1
Client B: SET counter 1      ← Lost update! Should be 2
```

### 11.2 Counter Patterns

```python
class MultiGranularityCounter:
    """Track counts at multiple time granularities efficiently."""
    
    def __init__(self, redis_client):
        self.r = redis_client
    
    def increment(self, metric: str, value: int = 1):
        now = time.time()
        minute = int(now // 60) * 60
        hour = int(now // 3600) * 3600
        day = int(now // 86400) * 86400
        
        pipe = self.r.pipeline()
        
        # Minute granularity (keep 24 hours)
        minute_key = f"counter:{metric}:m:{minute}"
        pipe.incrby(minute_key, value)
        pipe.expire(minute_key, 86400)
        
        # Hour granularity (keep 30 days)
        hour_key = f"counter:{metric}:h:{hour}"
        pipe.incrby(hour_key, value)
        pipe.expire(hour_key, 86400 * 30)
        
        # Day granularity (keep 365 days)
        day_key = f"counter:{metric}:d:{day}"
        pipe.incrby(day_key, value)
        pipe.expire(day_key, 86400 * 365)
        
        # Total (no expiry)
        pipe.incrby(f"counter:{metric}:total", value)
        
        pipe.execute()
    
    def get_range(self, metric: str, granularity: str, 
                  start_ts: int, end_ts: int) -> list:
        if granularity == "minute":
            step = 60
            prefix = "m"
        elif granularity == "hour":
            step = 3600
            prefix = "h"
        else:
            step = 86400
            prefix = "d"
        
        keys = []
        ts = (start_ts // step) * step
        while ts <= end_ts:
            keys.append(f"counter:{metric}:{prefix}:{ts}")
            ts += step
        
        values = self.r.mget(keys)
        return [(keys[i], int(v) if v else 0) for i, v in enumerate(values)]


# Usage
counter = MultiGranularityCounter(r)
counter.increment("api:requests:/users")
counter.increment("api:requests:/users", 5)
```

### 11.3 Atomic Counter with Bounds (Lua)

```python
# Decrement stock but never go below 0
lua_script = """
local current = redis.call('GET', KEYS[1])
if current == false then
    return -1
end
current = tonumber(current)
local amount = tonumber(ARGV[1])
if current < amount then
    return -2
end
redis.call('DECRBY', KEYS[1], amount)
return current - amount
"""

def safe_decrement_stock(product_id: str, quantity: int) -> int:
    result = r.execute_command(
        "EVAL", lua_script, 1,
        f"stock:{product_id}", str(quantity)
    )
    if result == -1:
        raise ValueError("Product not found")
    if result == -2:
        raise ValueError("Insufficient stock")
    return result

# Set initial stock
r.set("stock:PROD-001", "50")
remaining = safe_decrement_stock("PROD-001", 3)  # 47
```

---

## 12. Locking & Distributed Locks

### 12.1 The Problem

In distributed systems, multiple processes/services need exclusive access to shared resources. Without coordination, concurrent access causes:
- Double-spending (two payments for one order)
- Overselling (stock goes negative)
- Data corruption (concurrent writes to same record)

### 12.2 Simple Lock — SET NX EX

```python
import uuid
import time

class RedisLock:
    def __init__(self, redis_client, resource: str, ttl: int = 30):
        self.r = redis_client
        self.resource = resource
        self.key = f"lock:{resource}"
        self.ttl = ttl
        self.token = str(uuid.uuid4())  # Unique owner identifier
    
    def acquire(self, timeout: int = 10) -> bool:
        """Attempt to acquire lock with retry."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            # SET key value NX EX ttl — atomic "set if not exists with expiry"
            acquired = self.r.set(self.key, self.token, nx=True, ex=self.ttl)
            if acquired:
                return True
            time.sleep(0.05)  # Small backoff
        return False
    
    def release(self) -> bool:
        """Release lock ONLY if we still own it (compare-and-delete)."""
        # CRITICAL: Must use Lua for atomic check-and-delete
        # Otherwise another client might acquire between our GET and DEL
        lua_release = """
        if redis.call('GET', KEYS[1]) == ARGV[1] then
            return redis.call('DEL', KEYS[1])
        else
            return 0
        end
        """
        result = self.r.execute_command(
            "EVAL", lua_release, 1,
            self.key, self.token
        )
        return result == 1
    
    def extend(self, additional_seconds: int) -> bool:
        """Extend lock TTL if we still own it."""
        lua_extend = """
        if redis.call('GET', KEYS[1]) == ARGV[1] then
            return redis.call('PEXPIRE', KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        result = self.r.execute_command(
            "EVAL", lua_extend, 1,
            self.key, self.token, str(additional_seconds * 1000)
        )
        return result == 1
    
    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(f"Could not acquire lock on {self.resource}")
        return self
    
    def __exit__(self, *args):
        self.release()


# Usage
lock = RedisLock(r, "order:5001:process")
with lock:
    # Only one worker executes this at a time
    process_order("5001")
```

### 12.3 Why the Token Matters

Without a unique token, a dangerous scenario occurs:

```
1. Client A acquires lock (TTL=30s)
2. Client A gets slow (GC pause, network delay) — 35 seconds pass
3. Lock expires automatically
4. Client B acquires lock (legitimately)
5. Client A finishes, calls DEL lock — DELETES CLIENT B'S LOCK!
6. Client C now acquires — both B and C think they have the lock
```

With a token: Client A's release checks `GET lock == A's_token` — fails because the value is now B's token. B's lock is safe.

### 12.4 Lock with Automatic Renewal (Watchdog)

```python
import threading

class RenewableLock:
    def __init__(self, redis_client, resource: str, ttl: int = 30):
        self.r = redis_client
        self.key = f"lock:{resource}"
        self.ttl = ttl
        self.token = str(uuid.uuid4())
        self._renewal_thread = None
        self._stop_renewal = threading.Event()
    
    def acquire(self, timeout: int = 10) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.r.set(self.key, self.token, nx=True, ex=self.ttl):
                self._start_renewal()
                return True
            time.sleep(0.05)
        return False
    
    def _start_renewal(self):
        """Background thread extends TTL at ttl/3 intervals."""
        self._stop_renewal.clear()
        
        def renew():
            while not self._stop_renewal.is_set():
                self._stop_renewal.wait(self.ttl / 3)
                if self._stop_renewal.is_set():
                    break
                lua_extend = """
                if redis.call('GET', KEYS[1]) == ARGV[1] then
                    return redis.call('PEXPIRE', KEYS[1], ARGV[2])
                else
                    return 0
                end
                """
                result = self.r.execute_command(
                    "EVAL", lua_extend, 1,
                    self.key, self.token, str(self.ttl * 1000)
                )
                if result == 0:
                    break  # Lost the lock
        
        self._renewal_thread = threading.Thread(target=renew, daemon=True)
        self._renewal_thread.start()
    
    def release(self):
        self._stop_renewal.set()
        lua_release = """
        if redis.call('GET', KEYS[1]) == ARGV[1] then
            return redis.call('DEL', KEYS[1])
        else
            return 0
        end
        """
        self.r.execute_command("EVAL", lua_release, 1, self.key, self.token)
```

### 12.5 Redlock — Multi-Node Distributed Lock

For single Redis instances, the lock above is sufficient. But if that Redis dies, all locks are lost. Redlock uses N independent Redis masters (typically 5) for fault tolerance.

```python
class Redlock:
    """
    Redlock algorithm (Antirez, 2014):
    1. Get current time
    2. Try to acquire lock on N/2+1 out of N Redis nodes
    3. Calculate elapsed time — if total < TTL and majority acquired, lock is valid
    4. If lock fails, release on ALL nodes
    """
    
    def __init__(self, redis_clients: list, resource: str, ttl: int = 30):
        self.clients = redis_clients  # List of independent Redis connections
        self.resource = resource
        self.key = f"lock:{resource}"
        self.ttl = ttl
        self.token = str(uuid.uuid4())
        self.quorum = len(redis_clients) // 2 + 1  # Majority
        # Clock drift compensation: small fraction of TTL
        self.clock_drift_factor = 0.01
    
    def acquire(self) -> bool:
        start_time = time.time()
        acquired_count = 0
        
        for client in self.clients:
            try:
                if client.set(self.key, self.token, nx=True, px=self.ttl * 1000):
                    acquired_count += 1
            except redis.ConnectionError:
                continue  # Node is down — skip it
        
        # Calculate elapsed time
        elapsed_ms = (time.time() - start_time) * 1000
        drift = self.ttl * 1000 * self.clock_drift_factor + 2  # ms
        validity_time = (self.ttl * 1000) - elapsed_ms - drift
        
        if acquired_count >= self.quorum and validity_time > 0:
            return True
        else:
            # Failed — release on all nodes
            self._release_all()
            return False
    
    def release(self):
        self._release_all()
    
    def _release_all(self):
        lua_release = """
        if redis.call('GET', KEYS[1]) == ARGV[1] then
            return redis.call('DEL', KEYS[1])
        else
            return 0
        end
        """
        for client in self.clients:
            try:
                client.execute_command(
                    "EVAL", lua_release, 1,
                    self.key, self.token
                )
            except redis.ConnectionError:
                continue


# Usage with 5 independent Redis nodes
nodes = [
    redis.Redis(host='redis1', port=6379),
    redis.Redis(host='redis2', port=6379),
    redis.Redis(host='redis3', port=6379),
    redis.Redis(host='redis4', port=6379),
    redis.Redis(host='redis5', port=6379),
]

lock = Redlock(nodes, "critical:payment:ORD-5001", ttl=30)
if lock.acquire():
    try:
        process_payment("ORD-5001")
    finally:
        lock.release()
```

### 12.6 Fencing Tokens — Defense Against Stale Locks

Even with Redlock, a client might believe it holds a lock when it doesn't (GC pause after acquisition, before critical section). Fencing tokens solve this:

```python
class FencedLock:
    """Lock with monotonically increasing fencing token."""
    
    def __init__(self, redis_client, resource: str, ttl: int = 30):
        self.r = redis_client
        self.resource = resource
        self.lock_key = f"lock:{resource}"
        self.fence_key = f"fence:{resource}"
        self.ttl = ttl
        self.token = str(uuid.uuid4())
        self.fencing_token = None
    
    def acquire(self) -> int:
        """Returns fencing token (monotonically increasing int) on success, None on failure."""
        acquired = self.r.set(self.lock_key, self.token, nx=True, ex=self.ttl)
        if not acquired:
            return None
        
        # Generate monotonically increasing fencing token
        self.fencing_token = self.r.incr(self.fence_key)
        return self.fencing_token
    
    def release(self):
        lua_release = """
        if redis.call('GET', KEYS[1]) == ARGV[1] then
            return redis.call('DEL', KEYS[1])
        else
            return 0
        end
        """
        self.r.execute_command("EVAL", lua_release, 1, self.lock_key, self.token)


# The protected resource checks the fencing token:
def write_to_storage(data, fencing_token: int):
    """Storage rejects writes with stale fencing tokens."""
    current_max = get_max_fencing_token_from_storage()
    if fencing_token <= current_max:
        raise StaleTokenError("Lock was superseded")
    # Proceed with write, store fencing_token
    do_write(data, fencing_token)
```

### 12.7 Lock Comparison Table

| Pattern | Safety | Liveness | Use Case |
|---------|--------|----------|----------|
| SET NX EX (single node) | Safe if one Redis | TTL auto-release | Most apps, single-master |
| SET NX EX + Watchdog | Same + no premature expiry | Renewal prevents loss | Long tasks |
| Redlock (N nodes) | Tolerates N/2-1 failures | Quorum + TTL | Critical distributed systems |
| Fencing Token | Strongest (detects stale) | Same as above | Financial, exactly-once |

---

## 13. Lua Scripting

Lua scripts execute atomically in Redis — the server processes the entire script without interruption. This enables complex atomic operations impossible with single commands.

### 13.1 Basic Lua Execution

```python
# Simple script: return a value
lua_script = """
return "Hello from Lua!"
"""
result = r.execute_command("EVAL", lua_script, 0)
# "Hello from Lua!"

# Script with KEYS and ARGV
lua_script = """
local key = KEYS[1]
local value = ARGV[1]
local ttl = tonumber(ARGV[2])
redis.call('SET', key, value)
redis.call('EXPIRE', key, ttl)
return redis.call('GET', key)
"""
result = r.execute_command(
    "EVAL", lua_script, 1,       # 1 key
    "my:key", "my_value", "60"   # KEYS[1], ARGV[1], ARGV[2]
)
```

### 13.2 Compare-And-Swap (CAS) with Lua

```python
# Atomic: read current value, validate, update
lua_cas = """
local key = KEYS[1]
local expected = ARGV[1]
local new_value = ARGV[2]
local current = redis.call('GET', key)
if current == expected then
    redis.call('SET', key, new_value)
    return 1
else
    return 0
end
"""

def compare_and_swap(key: str, expected: str, new_value: str) -> bool:
    result = r.execute_command("EVAL", lua_cas, 1, key, expected, new_value)
    return result == 1
```

### 13.3 Atomic Rate Limiter (Sliding Window in Lua)

```python
lua_rate_limit = """
local key = KEYS[1]
local window = tonumber(ARGV[1])
local max_requests = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local window_start = now - window

-- Remove entries outside window
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

-- Count current entries
local current = redis.call('ZCARD', key)

if current < max_requests then
    -- Add this request
    redis.call('ZADD', key, now, now .. ':' .. math.random(1000000))
    redis.call('EXPIRE', key, window)
    return 1  -- Allowed
else
    return 0  -- Denied
end
"""

def check_rate_limit(user_id: str, max_requests: int = 100, 
                     window_seconds: int = 60) -> bool:
    key = f"ratelimit:{user_id}"
    now = time.time()
    result = r.execute_command(
        "EVAL", lua_rate_limit, 1,
        key, str(window_seconds), str(max_requests), str(now)
    )
    return result == 1
```

### 13.4 EVALSHA — Script Caching

```python
import hashlib

# First time: EVAL sends full script (costly for large scripts)
# After that: EVALSHA sends only the SHA1 hash

lua_script = """
local current = redis.call('INCRBY', KEYS[1], ARGV[1])
if current == tonumber(ARGV[1]) then
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
end
return current
"""

# Load script and get SHA
sha = r.script_load(lua_script)

# Execute by SHA (much faster, no script transmission)
result = r.evalsha(sha, 1, "counter:daily", "1", "86400")

# If script not cached on this node (e.g., after failover):
try:
    result = r.evalsha(sha, 1, "counter:daily", "1", "86400")
except redis.exceptions.NoScriptError:
    # Fall back to full EVAL (re-caches the script)
    result = r.execute_command("EVAL", lua_script, 1, "counter:daily", "1", "86400")
```

---

## 14. Pub/Sub

Redis Pub/Sub provides fire-and-forget messaging. Messages are NOT persisted — if no subscriber is listening, the message is lost.

### 14.1 Basic Pub/Sub

```python
# Publisher
r.publish("notifications:user:1001", json.dumps({
    "type": "order_shipped",
    "order_id": "ORD-5001",
    "eta": "2026-01-17"
}))

# Subscriber (blocking — runs in its own thread/process)
import json

pubsub = r.pubsub()
pubsub.subscribe("notifications:user:1001")

for message in pubsub.listen():
    if message["type"] == "message":
        data = json.loads(message["data"])
        print(f"Received: {data}")

# Pattern subscribe (wildcard)
pubsub.psubscribe("notifications:user:*")
for message in pubsub.listen():
    if message["type"] == "pmessage":
        channel = message["channel"]  # e.g., "notifications:user:1001"
        data = json.loads(message["data"])
        user_id = channel.split(":")[2]
        handle_notification(user_id, data)
```

### 14.2 Pub/Sub vs Streams

| Feature | Pub/Sub | Streams |
|---------|---------|---------|
| Persistence | No | Yes |
| Consumer Groups | No | Yes |
| Replay | No | Yes (from any ID) |
| Acknowledgment | No | Yes (XACK) |
| At-most-once | Yes | At-least-once |
| Fan-out | All subscribers get all messages | One consumer per group per message |

**Rule**: Use Pub/Sub for real-time notifications where loss is acceptable. Use Streams for reliable message processing.

---

## 15. Geospatial

Redis Geo commands store longitude/latitude pairs and perform radius/distance queries. Under the hood, it uses a Sorted Set with geohash encoding.

### 15.1 GEOADD / GEOPOS / GEODIST

```python
# GEOADD — add locations (lng, lat, member)
r.geoadd("restaurants:mumbai", [
    72.8777, 19.0760, "restaurant:001",   # Gateway of India area
    72.8296, 19.1071, "restaurant:002",   # Bandra
    72.8562, 19.0176, "restaurant:003",   # Colaba
])

# GEOPOS — get coordinates of a member
pos = r.geopos("restaurants:mumbai", "restaurant:001")
# [(72.8777, 19.076)]

# GEODIST — distance between two members
dist = r.geodist("restaurants:mumbai", "restaurant:001", "restaurant:002", unit="km")
# Distance in km
# Units: m (meters), km, mi (miles), ft (feet)
```

### 15.2 GEOSEARCH — Find Nearby (Redis 6.2+)

```python
# Find restaurants within 5km of a point
nearby = r.geosearch(
    "restaurants:mumbai",
    longitude=72.8777, latitude=19.0760,
    radius=5, unit="km",
    sort="ASC",  # Nearest first
    count=10,
    withcoord=True,
    withdist=True
)
# Returns: [(member, distance, (lng, lat)), ...]

# Find restaurants within a rectangular box
in_box = r.geosearch(
    "restaurants:mumbai",
    longitude=72.85, latitude=19.05,
    width=10, height=10, unit="km",
    sort="ASC"
)

# Search from an existing member (not a coordinate)
near_restaurant_001 = r.geosearch(
    "restaurants:mumbai",
    member="restaurant:001",
    radius=3, unit="km",
    sort="ASC",
    withcoord=True,
    withdist=True
)
```

### 15.3 GEOSEARCHSTORE — Store Results

```python
# Store nearby results into a new sorted set
r.geosearchstore(
    "nearby:user:1001",           # Destination key
    "restaurants:mumbai",          # Source key
    longitude=72.8777, latitude=19.0760,
    radius=5, unit="km",
    count=20,
    storedist=True  # Store distances as scores (instead of geohash)
)

# Now you can paginate the results using ZRANGE
page_1 = r.zrange("nearby:user:1001", 0, 9, withscores=True)
# Returns restaurants sorted by distance
```

---

## Quick Reference — Time Complexity

| Command | Type | Complexity |
|---------|------|-----------|
| SET/GET | String | O(1) |
| MSET/MGET | String | O(N) |
| INCR/DECR | String | O(1) |
| HSET/HGET | Hash | O(1) |
| HGETALL | Hash | O(N) |
| LPUSH/RPUSH/LPOP/RPOP | List | O(1) |
| LRANGE | List | O(S+N) |
| LINDEX | List | O(N) |
| SADD/SREM/SISMEMBER | Set | O(1) |
| SMEMBERS | Set | O(N) |
| SUNION/SINTER/SDIFF | Set | O(N*M) |
| ZADD/ZREM | Sorted Set | O(log N) |
| ZRANGE/ZREVRANGE | Sorted Set | O(log N + M) |
| ZSCORE/ZRANK | Sorted Set | O(1) / O(log N) |
| PFADD/PFCOUNT | HyperLogLog | O(1) |
| XADD/XREAD | Stream | O(1) / O(N) |
| SCAN/HSCAN/SSCAN/ZSCAN | All | O(1) per call |

---

## Anti-Patterns to Avoid

1. **KEYS * in production** — Blocks Redis while scanning all keys. Use SCAN instead.
2. **Large HGETALL** — Fetching 100K fields blocks the event loop. Use HSCAN.
3. **Unbounded lists** — Always LTRIM after LPUSH to prevent memory explosion.
4. **Missing TTL** — Keys without expiry accumulate forever. Always set TTL on transient data.
5. **Hot keys** — One key receiving millions of ops/sec becomes a bottleneck. Shard the key.
6. **Large values** — Values > 100KB cause network/memory pressure. Compress or split.
7. **SETNX + EXPIRE** — Two commands, not atomic. Use `SET key val NX EX ttl` instead.
8. **DEL on large keys** — Blocks while freeing memory. Use UNLINK for async deletion.
9. **SELECT (multiple databases)** — Not supported in Redis Cluster. Use key prefixes instead.
10. **Storing JSON as string** — Consider Redis Hashes for objects you need to partially read/update.
