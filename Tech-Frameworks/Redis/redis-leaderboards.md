# Redis Leaderboards — Sorted Sets in Production

## Why Redis for Leaderboards

Traditional databases struggle with leaderboard queries — `ORDER BY score DESC LIMIT 100` on millions of rows is expensive. Redis Sorted Sets give O(log N) insert/update and O(log N + M) range queries, making them ideal for real-time rankings.

**Core guarantee:** Every member has a unique score, and the set is always sorted. Ties are broken lexicographically by member name.

---

## 1. Sorted Set Internals

```
┌─────────────────────────────────────────────────┐
│           Sorted Set (ZSET)                      │
├─────────────────────────────────────────────────┤
│  Encoding: skiplist + hashtable (>128 elements)  │
│            listpack (<128 elements, <64B values) │
├─────────────────────────────────────────────────┤
│  Skiplist: O(log N) insert, delete, range        │
│  Hashtable: O(1) score lookup by member          │
│  Combined: best of both access patterns          │
└─────────────────────────────────────────────────┘
```

**Memory layout:** For small sets (< `zset-max-listpack-entries` = 128), Redis uses a compact listpack. Beyond that threshold, it switches to skiplist + dict for O(log N) operations.

---

## 2. Basic Leaderboard Operations

```python
import redis
import time

class Leaderboard:
    """Production leaderboard using Redis Sorted Sets."""

    def __init__(self, name: str, r: redis.Redis):
        self.key = f"leaderboard:{name}"
        self.r = r

    def update_score(self, user_id: str, score: float):
        """Set absolute score for a user. O(log N)."""
        self.r.zadd(self.key, {user_id: score})

    def increment_score(self, user_id: str, delta: float) -> float:
        """Atomically increment score. O(log N). Returns new score."""
        return self.r.zincrby(self.key, delta, user_id)

    def get_rank(self, user_id: str) -> int | None:
        """Get 0-based rank (highest score = rank 0). O(log N)."""
        rank = self.r.zrevrank(self.key, user_id)
        return rank  # None if user not in set

    def get_score(self, user_id: str) -> float | None:
        """Get user's current score. O(1)."""
        return self.r.zscore(self.key, user_id)

    def top_n(self, n: int = 10) -> list[tuple[str, float]]:
        """Get top N users with scores. O(log N + M)."""
        return self.r.zrevrange(self.key, 0, n - 1, withscores=True)

    def get_around_user(self, user_id: str, count: int = 5) -> list[tuple[str, float]]:
        """Get users around a specific user's rank. O(log N + M)."""
        rank = self.r.zrevrank(self.key, user_id)
        if rank is None:
            return []
        start = max(0, rank - count)
        end = rank + count
        return self.r.zrevrange(self.key, start, end, withscores=True)

    def total_players(self) -> int:
        """Total members in leaderboard. O(1)."""
        return self.r.zcard(self.key)

    def remove_user(self, user_id: str):
        """Remove user from leaderboard. O(log N)."""
        self.r.zrem(self.key, user_id)

    def rank_range(self, start: int, end: int) -> list[tuple[str, float]]:
        """Get users in rank range (0-based, inclusive). O(log N + M)."""
        return self.r.zrevrange(self.key, start, end, withscores=True)

    def score_range(self, min_score: float, max_score: float) -> list[tuple[str, float]]:
        """Get users within score range. O(log N + M)."""
        return self.r.zrevrangebyscore(
            self.key, max_score, min_score, withscores=True
        )
```

---

## 3. Time-Windowed Leaderboards

Real games/apps need daily, weekly, monthly leaderboards that auto-reset.

```python
from datetime import datetime, timedelta

class TimeWindowedLeaderboard:
    """Leaderboards that reset on time boundaries."""

    def __init__(self, name: str, r: redis.Redis):
        self.name = name
        self.r = r

    def _key(self, window: str) -> str:
        now = datetime.utcnow()
        if window == "daily":
            suffix = now.strftime("%Y-%m-%d")
            ttl = 86400 * 2  # keep 2 days
        elif window == "weekly":
            # ISO week
            suffix = f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"
            ttl = 86400 * 14
        elif window == "monthly":
            suffix = now.strftime("%Y-%m")
            ttl = 86400 * 62
        else:  # all-time
            suffix = "alltime"
            ttl = None
        key = f"lb:{self.name}:{window}:{suffix}"
        return key, ttl

    def record_score(self, user_id: str, score: float):
        """Update score across all time windows atomically."""
        pipe = self.r.pipeline()
        for window in ["daily", "weekly", "monthly", "alltime"]:
            key, ttl = self._key(window)
            pipe.zincrby(key, score, user_id)
            if ttl:
                pipe.expire(key, ttl)
        pipe.execute()

    def get_top(self, window: str, n: int = 10) -> list[tuple[str, float]]:
        key, _ = self._key(window)
        return self.r.zrevrange(key, 0, n - 1, withscores=True)

    def get_user_ranks(self, user_id: str) -> dict:
        """Get user's rank across all windows."""
        pipe = self.r.pipeline()
        windows = ["daily", "weekly", "monthly", "alltime"]
        for window in windows:
            key, _ = self._key(window)
            pipe.zrevrank(key, user_id)
        results = pipe.execute()
        return dict(zip(windows, results))
```

**TTL strategy:** Set TTL slightly longer than the window to handle timezone edge cases. Old leaderboards auto-expire — no cron cleanup needed.

---

## 4. Composite Score Leaderboards

When you need secondary sort criteria (e.g., same score → earlier timestamp wins):

```python
class CompositeScoreLeaderboard:
    """
    Encode multiple sort criteria into a single float score.
    
    Strategy: score = primary_score + (1 - normalized_timestamp)
    
    Example: Player with 100 points at t=1000 gets score 100.999000
             Player with 100 points at t=2000 gets score 100.998000
             → First player ranks higher (earlier achievement)
    """

    MAX_TIMESTAMP = 10_000_000_000  # ~2286, far future

    def __init__(self, name: str, r: redis.Redis):
        self.key = f"lb:composite:{name}"
        self.r = r

    def update_score(self, user_id: str, primary_score: int):
        """
        Composite = primary_score + fractional_time_component.
        Higher primary score wins. On tie, earlier time wins.
        """
        timestamp = time.time()
        # Normalize timestamp to 0-1 range, invert so earlier = higher
        time_component = (self.MAX_TIMESTAMP - timestamp) / self.MAX_TIMESTAMP
        composite = primary_score + time_component
        self.r.zadd(self.key, {user_id: composite})

    def get_primary_score(self, user_id: str) -> int | None:
        """Extract the primary score from composite."""
        composite = self.r.zscore(self.key, user_id)
        if composite is None:
            return None
        return int(composite)  # truncate fractional part

    def top_n(self, n: int = 10) -> list[dict]:
        results = self.r.zrevrange(self.key, 0, n - 1, withscores=True)
        return [
            {"user_id": uid, "score": int(score), "rank": i + 1}
            for i, (uid, score) in enumerate(results)
        ]
```

**Alternative encoding for multiple dimensions:**
```python
def encode_multi_score(wins: int, kills: int, timestamp: float) -> float:
    """
    Encode: wins (primary) + kills (secondary) + time (tertiary).
    Each dimension gets a fixed number of decimal places.
    
    Score format: WWWWWW.KKKKKTTTTTT
    - Wins: up to 999,999
    - Kills: up to 99,999 (5 digits after decimal)
    - Time: 6 digits (inverted, lower = more recent)
    """
    time_component = (10_000_000_000 - int(timestamp)) % 1_000_000
    return wins + (kills / 100_000) + (time_component / 100_000_000_000)
```

---

## 5. Paginated Leaderboard with User Context

```python
class PaginatedLeaderboard:
    """Production leaderboard with pagination and surrounding context."""

    PAGE_SIZE = 25

    def __init__(self, name: str, r: redis.Redis):
        self.key = f"lb:{name}"
        self.r = r

    def get_page(self, page: int = 1) -> dict:
        """Get a specific page of the leaderboard."""
        start = (page - 1) * self.PAGE_SIZE
        end = start + self.PAGE_SIZE - 1

        pipe = self.r.pipeline()
        pipe.zrevrange(self.key, start, end, withscores=True)
        pipe.zcard(self.key)
        entries, total = pipe.execute()

        total_pages = (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE

        return {
            "page": page,
            "total_pages": total_pages,
            "total_players": total,
            "entries": [
                {"rank": start + i + 1, "user_id": uid, "score": score}
                for i, (uid, score) in enumerate(entries)
            ],
        }

    def get_user_context(self, user_id: str) -> dict:
        """
        Get user's rank + surrounding players.
        Useful for "You are #4523 — here's who's around you."
        """
        pipe = self.r.pipeline()
        pipe.zrevrank(self.key, user_id)
        pipe.zscore(self.key, user_id)
        pipe.zcard(self.key)
        rank, score, total = pipe.execute()

        if rank is None:
            return {"found": False}

        # Get 2 above and 2 below
        context_start = max(0, rank - 2)
        context_end = min(total - 1, rank + 2)

        entries = self.r.zrevrange(
            self.key, context_start, context_end, withscores=True
        )

        return {
            "found": True,
            "user_rank": rank + 1,  # 1-based for display
            "user_score": score,
            "total_players": total,
            "percentile": round((1 - rank / total) * 100, 1),
            "context": [
                {
                    "rank": context_start + i + 1,
                    "user_id": uid,
                    "score": s,
                    "is_self": uid == user_id,
                }
                for i, (uid, s) in enumerate(entries)
            ],
        }
```

---

## 6. Multi-Leaderboard Aggregation

Combine scores from multiple activities into a unified ranking:

```python
class AggregatedLeaderboard:
    """
    Combine multiple score sources into one leaderboard.
    Uses ZUNIONSTORE for server-side aggregation.
    """

    def __init__(self, r: redis.Redis):
        self.r = r

    def aggregate(
        self,
        destination: str,
        sources: dict[str, float],
        aggregate: str = "SUM",
    ):
        """
        Combine multiple sorted sets with weights.
        
        Example:
            sources = {
                "lb:kills": 2.0,    # kills weighted 2x
                "lb:assists": 1.0,
                "lb:wins": 5.0,     # wins weighted 5x
            }
        
        aggregate options: SUM, MIN, MAX
        """
        keys = list(sources.keys())
        weights = [sources[k] for k in keys]

        # ZUNIONSTORE dst numkeys key1 key2 ... WEIGHTS w1 w2 ... AGGREGATE SUM
        self.r.zunionstore(destination, keys=sources, aggregate=aggregate)
        # Set TTL so aggregated board auto-refreshes
        self.r.expire(destination, 300)  # 5 min cache

    def rebuild_weekly_combined(self):
        """Example: combine multiple activity scores into weekly leaderboard."""
        self.aggregate(
            destination="lb:weekly:combined",
            sources={
                "lb:weekly:matches_won": 10.0,
                "lb:weekly:kills": 1.0,
                "lb:weekly:objectives": 5.0,
                "lb:weekly:assists": 0.5,
            },
        )

    def intersect_leaderboards(self, destination: str, sources: list[str]):
        """
        ZINTERSTORE: only users present in ALL source leaderboards.
        Useful for "players who participated in all game modes."
        """
        self.r.zinterstore(destination, keys=sources, aggregate="SUM")
        self.r.expire(destination, 300)
```

**ZUNIONSTORE vs ZINTERSTORE:**
- UNION: Player appears if they're in ANY source set. Missing scores default to 0.
- INTERSECT: Player must appear in ALL source sets. Stricter but fairer for "all-rounder" leaderboards.

---

## 7. Real-Time Leaderboard Updates with Pub/Sub

```python
import json
import threading

class LiveLeaderboard:
    """
    Leaderboard that broadcasts rank changes to connected clients.
    Useful for real-time UI updates via WebSocket.
    """

    def __init__(self, name: str, r: redis.Redis):
        self.key = f"lb:{name}"
        self.channel = f"lb_updates:{name}"
        self.r = r

    def update_and_notify(self, user_id: str, new_score: float):
        """Update score and broadcast change."""
        pipe = self.r.pipeline()
        # Get old rank before update
        pipe.zrevrank(self.key, user_id)
        pipe.zscore(self.key, user_id)
        old_rank, old_score = pipe.execute()

        # Update score
        self.r.zadd(self.key, {user_id: new_score})

        # Get new rank after update
        new_rank = self.r.zrevrank(self.key, user_id)

        # Broadcast the change
        event = json.dumps({
            "type": "rank_change",
            "user_id": user_id,
            "old_rank": old_rank + 1 if old_rank is not None else None,
            "new_rank": new_rank + 1 if new_rank is not None else None,
            "old_score": old_score,
            "new_score": new_score,
            "timestamp": time.time(),
        })
        self.r.publish(self.channel, event)

    def subscribe_updates(self, callback):
        """Subscribe to leaderboard changes (run in thread)."""
        pubsub = self.r.pubsub()
        pubsub.subscribe(self.channel)

        for message in pubsub.listen():
            if message["type"] == "message":
                event = json.loads(message["data"])
                callback(event)
```

---

## 8. Sharded Leaderboard for Scale

For leaderboards with 100M+ entries, a single sorted set becomes a bottleneck:

```python
import hashlib

class ShardedLeaderboard:
    """
    Distribute users across N shards.
    Trade-off: exact global rank unavailable, but O(log(N/S)) per shard.
    
    Architecture:
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │ Shard 0  │   │ Shard 1  │   │ Shard 2  │  ... N shards
    │ (ZSET)   │   │ (ZSET)   │   │ (ZSET)   │
    └──────────┘   └──────────┘   └──────────┘
         │              │              │
         └──────────────┼──────────────┘
                        │
                  Approximate Rank = 
                  shard_rank * num_shards
    """

    def __init__(self, name: str, num_shards: int, r: redis.Redis):
        self.name = name
        self.num_shards = num_shards
        self.r = r

    def _shard_key(self, user_id: str) -> str:
        shard = int(hashlib.md5(user_id.encode()).hexdigest(), 16) % self.num_shards
        return f"lb:{self.name}:shard:{shard}"

    def update_score(self, user_id: str, score: float):
        key = self._shard_key(user_id)
        self.r.zadd(key, {user_id: score})

    def get_approximate_rank(self, user_id: str) -> int | None:
        """
        Approximate global rank.
        Exact rank within shard * num_shards gives rough position.
        """
        key = self._shard_key(user_id)
        shard_rank = self.r.zrevrank(key, user_id)
        if shard_rank is None:
            return None
        # Approximate: actual rank is roughly shard_rank * num_shards
        return shard_rank * self.num_shards

    def global_top_n(self, n: int) -> list[tuple[str, float]]:
        """
        Get global top N by merging shard tops.
        Fetch top N from each shard, merge client-side, take top N.
        """
        pipe = self.r.pipeline()
        for i in range(self.num_shards):
            pipe.zrevrange(f"lb:{self.name}:shard:{i}", 0, n - 1, withscores=True)
        shard_results = pipe.execute()

        # Merge all shard results
        all_entries = []
        for entries in shard_results:
            all_entries.extend(entries)

        # Sort by score descending, take top N
        all_entries.sort(key=lambda x: x[1], reverse=True)
        return all_entries[:n]
```

---

## 9. Leaderboard with Metadata Enrichment

Sorted Sets only store member → score. Enrich with user data at read time:

```python
class EnrichedLeaderboard:
    """
    Pattern: ZSET for ranking + HASH for user metadata.
    
    lb:game:weekly → sorted set (user_id → score)
    user:{user_id}  → hash (name, avatar, level, clan)
    """

    def __init__(self, name: str, r: redis.Redis):
        self.key = f"lb:{name}"
        self.r = r

    def get_enriched_top(self, n: int = 10) -> list[dict]:
        """Get top N with full user profiles (pipelined)."""
        # Step 1: Get top user IDs + scores
        top_entries = self.r.zrevrange(self.key, 0, n - 1, withscores=True)
        if not top_entries:
            return []

        # Step 2: Batch-fetch all user profiles
        pipe = self.r.pipeline()
        for user_id, _ in top_entries:
            pipe.hgetall(f"user:{user_id}")
        profiles = pipe.execute()

        # Step 3: Combine
        results = []
        for i, (user_id, score) in enumerate(top_entries):
            profile = profiles[i] or {}
            results.append({
                "rank": i + 1,
                "user_id": user_id,
                "score": score,
                "name": profile.get("name", "Unknown"),
                "avatar": profile.get("avatar", ""),
                "level": int(profile.get("level", 0)),
                "clan": profile.get("clan", ""),
            })
        return results

    def get_friends_leaderboard(self, user_id: str, friend_ids: list[str]) -> list[dict]:
        """
        Friends-only leaderboard.
        Fetch scores for specific users, sort client-side.
        """
        all_ids = [user_id] + friend_ids
        pipe = self.r.pipeline()
        for uid in all_ids:
            pipe.zscore(self.key, uid)
        scores = pipe.execute()

        entries = [
            {"user_id": uid, "score": score}
            for uid, score in zip(all_ids, scores)
            if score is not None
        ]
        entries.sort(key=lambda x: x["score"], reverse=True)
        for i, entry in enumerate(entries):
            entry["rank"] = i + 1
            entry["is_self"] = entry["user_id"] == user_id
        return entries
```

---

## 10. Anti-Cheat and Score Validation

```python
class ValidatedLeaderboard:
    """Leaderboard with server-side score validation."""

    MAX_SCORE_PER_GAME = 1000
    MAX_DAILY_GAMES = 50

    def __init__(self, name: str, r: redis.Redis):
        self.key = f"lb:{name}"
        self.r = r

    def submit_score(self, user_id: str, score: float, game_id: str) -> dict:
        """
        Validate and record a score submission.
        Returns: {"accepted": bool, "reason": str}
        """
        # Check 1: Score within valid range
        if score < 0 or score > self.MAX_SCORE_PER_GAME:
            return {"accepted": False, "reason": "score_out_of_range"}

        # Check 2: Duplicate game submission
        dedup_key = f"lb:dedup:{user_id}:{game_id}"
        if not self.r.set(dedup_key, 1, nx=True, ex=86400):
            return {"accepted": False, "reason": "duplicate_submission"}

        # Check 3: Rate limit (max games per day)
        daily_key = f"lb:daily_count:{user_id}"
        count = self.r.incr(daily_key)
        if count == 1:
            self.r.expire(daily_key, 86400)
        if count > self.MAX_DAILY_GAMES:
            return {"accepted": False, "reason": "daily_limit_exceeded"}

        # Check 4: Anomaly detection (sudden score spike)
        current_score = self.r.zscore(self.key, user_id) or 0
        if score > current_score * 10 and current_score > 100:
            # Flag for review, don't reject outright
            self.r.sadd("lb:flagged_users", user_id)

        # Accept the score
        self.r.zincrby(self.key, score, user_id)

        # Log for audit trail
        self.r.xadd(
            f"lb:audit:{user_id}",
            {"game_id": game_id, "score": str(score), "ts": str(time.time())},
            maxlen=1000,
        )

        return {"accepted": True, "reason": "ok"}
```

---

## 11. Leaderboard TTL and Cleanup

```python
class ManagedLeaderboard:
    """Leaderboard with lifecycle management."""

    def __init__(self, r: redis.Redis):
        self.r = r

    def create_seasonal(self, season: str, duration_days: int) -> str:
        """Create a time-limited seasonal leaderboard."""
        key = f"lb:season:{season}"
        # Set TTL from creation
        self.r.expire(key, duration_days * 86400)
        # Track in registry
        self.r.hset("lb:registry", season, f"{time.time()}:{duration_days}")
        return key

    def prune_inactive_users(self, leaderboard_key: str, min_score: float = 0):
        """Remove users below minimum score threshold."""
        removed = self.r.zremrangebyscore(leaderboard_key, "-inf", min_score)
        return removed

    def trim_to_top_n(self, leaderboard_key: str, n: int):
        """Keep only top N users, remove the rest."""
        # Remove all ranks below N (0-indexed)
        removed = self.r.zremrangebyrank(leaderboard_key, 0, -(n + 1))
        return removed

    def archive_leaderboard(self, source_key: str, archive_key: str):
        """Copy current leaderboard to archive before reset."""
        # COPY command (Redis 6.2+)
        self.r.copy(source_key, archive_key, replace=True)
        self.r.expire(archive_key, 86400 * 90)  # Keep archive 90 days
```

---

## 12. Performance Characteristics

| Operation | Command | Time Complexity |
|-----------|---------|-----------------|
| Add/update score | `ZADD` | O(log N) |
| Increment score | `ZINCRBY` | O(log N) |
| Get rank | `ZREVRANK` | O(log N) |
| Get score | `ZSCORE` | O(1) |
| Top N | `ZREVRANGE` | O(log N + M) |
| Score range | `ZRANGEBYSCORE` | O(log N + M) |
| Remove user | `ZREM` | O(log N) |
| Count members | `ZCARD` | O(1) |
| Union/Intersect | `ZUNIONSTORE` | O(N*K + M*log M) |
| Remove by rank | `ZREMRANGEBYRANK` | O(log N + M) |

**Memory:** ~80 bytes per member (skiplist overhead) + member string + 8 bytes for score.

**Benchmark:** A single Redis instance handles ~100K ZADD/sec and ~200K ZREVRANGE/sec on modern hardware.

---

## 13. Production Patterns Summary

```
┌─────────────────────────────────────────────────────────────┐
│                  Leaderboard Architecture                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────┐  │
│  │ Game     │───▶│ Validate │───▶│ ZINCRBY lb:daily     │  │
│  │ Server   │    │ Score    │    │ ZINCRBY lb:weekly    │  │
│  └──────────┘    └──────────┘    │ ZINCRBY lb:alltime   │  │
│                                   └──────────────────────┘  │
│                                              │               │
│                                              ▼               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Read Path (Pipelined)                     │   │
│  │  ZREVRANGE (top N) + HGETALL (profiles) → enriched   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Background Jobs                           │   │
│  │  • ZUNIONSTORE for aggregated boards (every 5 min)    │   │
│  │  • ZREMRANGEBYRANK to trim (daily)                    │   │
│  │  • COPY to archive (end of season)                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Key design decisions:**
1. **Separate ZSETs per time window** — avoids expensive recalculation
2. **Pipeline reads** — one round trip for rank + score + profile
3. **ZINCRBY over ZADD** — atomic, no read-modify-write race
4. **TTL on time-windowed keys** — self-cleaning, no cron
5. **ZUNIONSTORE for aggregation** — server-side, avoids transferring all data
6. **Friends board via ZSCORE + client sort** — cheaper than ZINTERSTORE for small friend lists
