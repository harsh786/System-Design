# Redis Feed Fanout & Notification Systems — Deep Dive

## Core Concepts

Feed fanout is the process of distributing a content item (post, activity, event) to all
interested recipients. Redis excels here because timeline operations (insert at head, trim,
paginate) map directly to sorted sets and lists.

**Two fundamental strategies:**
- **Fan-out on Write (push model):** When a user posts, immediately write to every follower's feed.
  Fast reads (O(1) per page), expensive writes for high-follower accounts.
- **Fan-out on Read (pull model):** Store posts per author; assemble the feed at read time by
  merging followed users' posts. Cheap writes, expensive reads.

**Hybrid approach (industry standard):** Fan-out on write for normal users, fan-out on read
for celebrities (users with >10K followers). This is what Twitter/X uses internally.

---

## 1. Fan-Out on Write — Push Model

```python
import redis
import time
import json
import uuid
from typing import Optional
from dataclasses import dataclass, asdict


@dataclass
class Post:
    post_id: str
    author_id: str
    content: str
    created_at: float
    media_urls: list = None
    mentions: list = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "Post":
        return cls(**json.loads(data))


class FanoutOnWriteEngine:
    """
    Push-based feed distribution.
    
    When a user publishes, we write the post_id into every follower's
    timeline sorted set. The score is the timestamp for chronological ordering.
    
    Data model:
      - post:{post_id}           → Hash (post content)
      - timeline:{user_id}       → Sorted Set (post_id scored by timestamp)
      - followers:{user_id}      → Set (who follows this user)
      - following:{user_id}      → Set (who this user follows)
    """

    def __init__(self, r: redis.Redis, max_timeline_size: int = 800):
        self.r = r
        self.max_timeline_size = max_timeline_size

        # Lua: Atomic fanout to a batch of followers
        # Adds post to each follower's timeline and trims excess
        self.FANOUT_BATCH_SCRIPT = """
        local post_id = ARGV[1]
        local score = ARGV[2]
        local max_size = tonumber(ARGV[3])
        local trimmed = 0

        for i = 1, #KEYS do
            redis.call('ZADD', KEYS[i], score, post_id)
            local size = redis.call('ZCARD', KEYS[i])
            if size > max_size then
                redis.call('ZREMRANGEBYRANK', KEYS[i], 0, size - max_size - 1)
                trimmed = trimmed + 1
            end
        end
        return trimmed
        """

    def publish_post(self, post: Post) -> dict:
        """
        Publish a post and fan out to all followers.
        
        For users with many followers, we batch the fanout into chunks
        to avoid blocking Redis with a single massive Lua script.
        """
        pipe = self.r.pipeline()

        # Store the post content
        post_key = f"post:{post.post_id}"
        pipe.hset(post_key, mapping={
            "post_id": post.post_id,
            "author_id": post.author_id,
            "content": post.content,
            "created_at": str(post.created_at),
            "media_urls": json.dumps(post.media_urls or []),
            "mentions": json.dumps(post.mentions or []),
        })
        # Post TTL: 30 days for content, timeline references persist independently
        pipe.expire(post_key, 30 * 86400)

        # Add to author's own timeline
        pipe.zadd(f"timeline:{post.author_id}", {post.post_id: post.created_at})
        pipe.execute()

        # Fan out to followers in batches
        followers = self.r.smembers(f"followers:{post.author_id}")
        stats = {"followers": len(followers), "batches": 0, "trimmed": 0}

        batch_size = 500  # Process 500 followers per Lua call
        follower_list = list(followers)

        for i in range(0, len(follower_list), batch_size):
            batch = follower_list[i:i + batch_size]
            keys = [f"timeline:{uid.decode()}" for uid in batch]

            trimmed = self.r.execute_command(
                "EVAL",
                self.FANOUT_BATCH_SCRIPT,
                len(keys),
                *keys,
                post.post_id,
                str(post.created_at),
                str(self.max_timeline_size),
            )
            stats["batches"] += 1
            stats["trimmed"] += trimmed

        return stats

    def get_timeline(self, user_id: str, offset: int = 0, limit: int = 20) -> list:
        """
        Retrieve a user's timeline with cursor-based pagination.
        Returns posts in reverse chronological order.
        """
        # Get post IDs from the timeline sorted set (highest score = newest)
        post_ids = self.r.zrevrange(
            f"timeline:{user_id}",
            offset,
            offset + limit - 1,
        )

        if not post_ids:
            return []

        # Batch fetch post content
        pipe = self.r.pipeline()
        for post_id in post_ids:
            pipe.hgetall(f"post:{post_id.decode()}")
        results = pipe.execute()

        posts = []
        for post_data in results:
            if post_data:  # Post might have expired
                post_data = {k.decode(): v.decode() for k, v in post_data.items()}
                post_data["media_urls"] = json.loads(post_data.get("media_urls", "[]"))
                post_data["mentions"] = json.loads(post_data.get("mentions", "[]"))
                post_data["created_at"] = float(post_data["created_at"])
                posts.append(post_data)

        return posts

    def delete_post(self, post: Post) -> int:
        """
        Remove a post from all followers' timelines.
        This is the expensive inverse of fanout — required for content moderation.
        """
        followers = self.r.smembers(f"followers:{post.author_id}")
        pipe = self.r.pipeline()

        # Remove from author's timeline
        pipe.zrem(f"timeline:{post.author_id}", post.post_id)
        # Remove from all followers' timelines
        for follower_id in followers:
            pipe.zrem(f"timeline:{follower_id.decode()}", post.post_id)
        # Delete post content
        pipe.delete(f"post:{post.post_id}")

        results = pipe.execute()
        return sum(1 for r in results[:-1] if r > 0)

    def follow_user(self, follower_id: str, followee_id: str, backfill: int = 50):
        """
        When user A follows user B, backfill A's timeline with B's recent posts.
        """
        pipe = self.r.pipeline()
        pipe.sadd(f"following:{follower_id}", followee_id)
        pipe.sadd(f"followers:{followee_id}", follower_id)
        pipe.execute()

        # Backfill: Get followee's recent posts and merge into follower's timeline
        recent_posts = self.r.zrevrange(
            f"timeline:{followee_id}", 0, backfill - 1, withscores=True
        )

        if recent_posts:
            timeline_key = f"timeline:{follower_id}"
            mapping = {post_id: score for post_id, score in recent_posts}
            self.r.zadd(timeline_key, mapping)

            # Trim if needed
            size = self.r.zcard(timeline_key)
            if size > self.max_timeline_size:
                self.r.zremrangebyrank(timeline_key, 0, size - self.max_timeline_size - 1)

    def unfollow_user(self, follower_id: str, followee_id: str):
        """
        When user A unfollows user B, remove B's posts from A's timeline.
        """
        pipe = self.r.pipeline()
        pipe.srem(f"following:{follower_id}", followee_id)
        pipe.srem(f"followers:{followee_id}", follower_id)
        pipe.execute()

        # Remove followee's posts from follower's timeline
        # Get all of followee's post IDs
        followee_posts = self.r.zrange(f"timeline:{followee_id}", 0, -1)
        if followee_posts:
            self.r.zrem(f"timeline:{follower_id}", *followee_posts)
```

---

## 2. Fan-Out on Read — Pull Model

```python
class FanoutOnReadEngine:
    """
    Pull-based feed assembly.
    
    Posts are stored only in the author's timeline. When a user requests their
    feed, we merge posts from all followed users in real-time.
    
    Data model:
      - user_posts:{user_id}  → Sorted Set (post_id scored by timestamp)
      - following:{user_id}   → Set (who this user follows)
      - feed_cache:{user_id}  → Sorted Set (cached assembled feed, short TTL)
    """

    MERGE_FEEDS_SCRIPT = """
    -- Merge multiple sorted sets into a destination with a limit
    -- KEYS[1] = destination key
    -- ARGV[1] = number of source keys
    -- ARGV[2] = limit (max items to keep)
    -- ARGV[3] = TTL for cache
    -- ARGV[4..] = source keys
    
    local dest = KEYS[1]
    local num_sources = tonumber(ARGV[1])
    local limit = tonumber(ARGV[2])
    local ttl = tonumber(ARGV[3])
    
    -- Collect source keys
    local sources = {}
    for i = 1, num_sources do
        sources[i] = ARGV[3 + i]
    end
    
    -- ZUNIONSTORE to merge all sources
    if num_sources > 0 then
        redis.call('ZUNIONSTORE', dest, num_sources, unpack(sources))
        -- Trim to keep only the most recent items
        local total = redis.call('ZCARD', dest)
        if total > limit then
            redis.call('ZREMRANGEBYRANK', dest, 0, total - limit - 1)
        end
        redis.call('EXPIRE', dest, ttl)
        return redis.call('ZCARD', dest)
    end
    return 0
    """

    def __init__(self, r: redis.Redis, cache_ttl: int = 60):
        self.r = r
        self.cache_ttl = cache_ttl  # Feed cache: 60 seconds

    def get_feed(self, user_id: str, offset: int = 0, limit: int = 20) -> list:
        """
        Assemble feed by merging posts from all followed users.
        Uses a short-lived cache to avoid repeated merges within seconds.
        """
        cache_key = f"feed_cache:{user_id}"

        # Check cache first
        cached = self.r.zrevrange(cache_key, offset, offset + limit - 1, withscores=True)
        if cached:
            return self._hydrate_posts(cached)

        # Cache miss — assemble feed
        following = self.r.smembers(f"following:{user_id}")
        if not following:
            return []

        source_keys = [f"user_posts:{uid.decode()}" for uid in following]
        # Also include user's own posts
        source_keys.append(f"user_posts:{user_id}")

        # Merge all sources into cache key
        self.r.execute_command(
            "EVAL",
            self.MERGE_FEEDS_SCRIPT,
            1,  # num keys (destination)
            cache_key,
            str(len(source_keys)),
            str(200),  # keep top 200 posts in cache
            str(self.cache_ttl),
            *source_keys,
        )

        # Read from freshly assembled cache
        results = self.r.zrevrange(cache_key, offset, offset + limit - 1, withscores=True)
        return self._hydrate_posts(results)

    def _hydrate_posts(self, post_id_scores: list) -> list:
        """Fetch full post content for a list of (post_id, score) tuples."""
        if not post_id_scores:
            return []

        pipe = self.r.pipeline()
        for post_id, _ in post_id_scores:
            pid = post_id.decode() if isinstance(post_id, bytes) else post_id
            pipe.hgetall(f"post:{pid}")
        results = pipe.execute()

        posts = []
        for i, post_data in enumerate(results):
            if post_data:
                decoded = {k.decode(): v.decode() for k, v in post_data.items()}
                decoded["score"] = post_id_scores[i][1]
                posts.append(decoded)
        return posts

    def publish_post(self, post: Post):
        """In pull model, just store in author's sorted set."""
        pipe = self.r.pipeline()
        pipe.hset(f"post:{post.post_id}", mapping={
            "post_id": post.post_id,
            "author_id": post.author_id,
            "content": post.content,
            "created_at": str(post.created_at),
        })
        pipe.zadd(f"user_posts:{post.author_id}", {post.post_id: post.created_at})
        # Invalidate cached feeds of followers
        followers = self.r.smembers(f"followers:{post.author_id}")
        for follower_id in followers:
            pipe.delete(f"feed_cache:{follower_id.decode()}")
        pipe.execute()
```

---

## 3. Hybrid Fanout — The Production Pattern

```python
class HybridFanoutEngine:
    """
    Combines push and pull models based on follower count thresholds.
    
    - Normal users (< 10K followers): Fan-out on write (push to all followers)
    - Celebrities (>= 10K followers): Fan-out on read (followers pull at read time)
    
    This is the pattern used by Twitter, Instagram, and LinkedIn at scale.
    
    Data model:
      - timeline:{user_id}        → Sorted Set (pushed posts from normal users)
      - celebrity_posts:{user_id} → Sorted Set (posts by celebrities, pulled at read)
      - celebrities:{user_id}     → Set (which followed users are celebrities)
      - user_meta:{user_id}       → Hash (follower_count, is_celebrity flag)
    """

    CELEBRITY_THRESHOLD = 10_000

    MERGE_TIMELINE_WITH_CELEBRITIES_SCRIPT = """
    -- KEYS[1] = user's push timeline
    -- KEYS[2] = temp merged key
    -- ARGV[1] = number of celebrity post keys
    -- ARGV[2] = limit
    -- ARGV[3] = TTL for temp key
    -- ARGV[4..] = celebrity post keys
    
    local timeline = KEYS[1]
    local dest = KEYS[2]
    local num_celeb_keys = tonumber(ARGV[1])
    local limit = tonumber(ARGV[2])
    local ttl = tonumber(ARGV[3])
    
    -- Start with user's push timeline
    local sources = {timeline}
    for i = 1, num_celeb_keys do
        sources[#sources + 1] = ARGV[3 + i]
    end
    
    -- Merge all into destination
    redis.call('ZUNIONSTORE', dest, #sources, unpack(sources))
    
    -- Trim to limit
    local total = redis.call('ZCARD', dest)
    if total > limit then
        redis.call('ZREMRANGEBYRANK', dest, 0, total - limit - 1)
    end
    redis.call('EXPIRE', dest, ttl)
    return total
    """

    def __init__(self, r: redis.Redis):
        self.r = r

    def publish_post(self, post: Post) -> dict:
        """Route to push or pull based on author's celebrity status."""
        follower_count = int(self.r.hget(f"user_meta:{post.author_id}", "follower_count") or 0)

        # Store post content
        self.r.hset(f"post:{post.post_id}", mapping={
            "post_id": post.post_id,
            "author_id": post.author_id,
            "content": post.content,
            "created_at": str(post.created_at),
        })
        self.r.expire(f"post:{post.post_id}", 30 * 86400)

        if follower_count >= self.CELEBRITY_THRESHOLD:
            return self._publish_celebrity(post)
        else:
            return self._publish_normal(post)

    def _publish_celebrity(self, post: Post) -> dict:
        """Celebrity: store in their post list only. Followers pull at read time."""
        self.r.zadd(
            f"celebrity_posts:{post.author_id}",
            {post.post_id: post.created_at},
        )
        # Trim to last 500 posts
        self.r.zremrangebyrank(f"celebrity_posts:{post.author_id}", 0, -501)
        return {"strategy": "pull", "fanout_count": 0}

    def _publish_normal(self, post: Post) -> dict:
        """Normal user: push to all followers' timelines."""
        followers = self.r.smembers(f"followers:{post.author_id}")
        if not followers:
            return {"strategy": "push", "fanout_count": 0}

        pipe = self.r.pipeline()
        for follower_id in followers:
            fid = follower_id.decode()
            pipe.zadd(f"timeline:{fid}", {post.post_id: post.created_at})
        pipe.execute()

        return {"strategy": "push", "fanout_count": len(followers)}

    def get_feed(self, user_id: str, offset: int = 0, limit: int = 20) -> list:
        """
        Assemble feed: merge push timeline with celebrity posts.
        """
        # Get list of celebrities this user follows
        celebrity_ids = self.r.smembers(f"celebrities:{user_id}")
        celebrity_keys = [f"celebrity_posts:{cid.decode()}" for cid in celebrity_ids]

        if celebrity_keys:
            # Merge push timeline with celebrity posts
            merged_key = f"merged_feed:{user_id}:{int(time.time())}"
            self.r.execute_command(
                "EVAL",
                self.MERGE_TIMELINE_WITH_CELEBRITIES_SCRIPT,
                2,  # KEYS: timeline + merged destination
                f"timeline:{user_id}",
                merged_key,
                str(len(celebrity_keys)),
                str(200),
                str(30),  # 30 second TTL for merged result
                *celebrity_keys,
            )
            # Read from merged result
            post_ids = self.r.zrevrange(merged_key, offset, offset + limit - 1)
        else:
            # No celebrities followed — just use push timeline
            post_ids = self.r.zrevrange(f"timeline:{user_id}", offset, offset + limit - 1)

        return self._hydrate_posts(post_ids)

    def _hydrate_posts(self, post_ids: list) -> list:
        if not post_ids:
            return []
        pipe = self.r.pipeline()
        for pid in post_ids:
            pipe.hgetall(f"post:{pid.decode()}")
        results = pipe.execute()

        posts = []
        for data in results:
            if data:
                posts.append({k.decode(): v.decode() for k, v in data.items()})
        return posts

    def promote_to_celebrity(self, user_id: str):
        """
        When a user crosses the celebrity threshold, update metadata
        and register them in all followers' celebrity sets.
        """
        self.r.hset(f"user_meta:{user_id}", "is_celebrity", "1")

        # Add to each follower's celebrity tracking set
        followers = self.r.smembers(f"followers:{user_id}")
        pipe = self.r.pipeline()
        for follower_id in followers:
            pipe.sadd(f"celebrities:{follower_id.decode()}", user_id)
        pipe.execute()

    def demote_from_celebrity(self, user_id: str):
        """Reverse: backfill recent posts into followers' push timelines."""
        self.r.hset(f"user_meta:{user_id}", "is_celebrity", "0")

        followers = self.r.smembers(f"followers:{user_id}")
        recent_posts = self.r.zrevrange(
            f"celebrity_posts:{user_id}", 0, 99, withscores=True
        )

        pipe = self.r.pipeline()
        for follower_id in followers:
            fid = follower_id.decode()
            pipe.srem(f"celebrities:{fid}", user_id)
            # Backfill posts into their push timeline
            if recent_posts:
                mapping = {pid: score for pid, score in recent_posts}
                pipe.zadd(f"timeline:{fid}", mapping)
        pipe.execute()
```

---

## 4. Activity Feed with Aggregation

```python
class ActivityFeedEngine:
    """
    Activity feeds (like GitHub, LinkedIn notifications) differ from content feeds:
    - Activities are aggregated: "Alice and 3 others liked your post"
    - Activities have types and targets
    - Recent activities for the same target are grouped
    
    Data model:
      - activity:{activity_id}           → Hash (activity content)
      - activity_feed:{user_id}          → Sorted Set (activity_ids by time)
      - activity_group:{user_id}:{target} → List (grouped activities for a target)
      - activity_unread:{user_id}        → String (timestamp of last read)
    """

    AGGREGATE_ACTIVITY_SCRIPT = """
    -- Atomically add an activity and update its aggregation group
    -- KEYS[1] = activity_feed:{user_id}
    -- KEYS[2] = activity_group:{user_id}:{target_key}
    -- KEYS[3] = activity:{activity_id}
    -- ARGV[1] = activity_id
    -- ARGV[2] = score (timestamp)
    -- ARGV[3] = group_key (used as the aggregated entry in the feed)
    -- ARGV[4] = max_group_size
    -- ARGV[5..] = activity hash fields (key, value pairs)
    
    local feed_key = KEYS[1]
    local group_key = KEYS[2]
    local activity_key = KEYS[3]
    local activity_id = ARGV[1]
    local score = ARGV[2]
    local group_id = ARGV[3]
    local max_group = tonumber(ARGV[4])
    
    -- Store activity details
    for i = 5, #ARGV, 2 do
        redis.call('HSET', activity_key, ARGV[i], ARGV[i+1])
    end
    redis.call('EXPIRE', activity_key, 7 * 86400)
    
    -- Add to aggregation group (list of activity IDs for this target)
    redis.call('LPUSH', group_key, activity_id)
    redis.call('LTRIM', group_key, 0, max_group - 1)
    redis.call('EXPIRE', group_key, 7 * 86400)
    
    -- Update the feed entry: use the group_id as the member, update score
    -- This means the group "floats up" when new activity arrives
    redis.call('ZADD', feed_key, score, group_id)
    
    -- Trim feed to 500 entries
    local total = redis.call('ZCARD', feed_key)
    if total > 500 then
        redis.call('ZREMRANGEBYRANK', feed_key, 0, total - 501)
    end
    
    return redis.call('LLEN', group_key)
    """

    def __init__(self, r: redis.Redis):
        self.r = r

    def add_activity(
        self,
        user_id: str,
        activity_type: str,
        actor_id: str,
        target_type: str,
        target_id: str,
        metadata: dict = None,
    ) -> int:
        """
        Add an activity to a user's feed with aggregation.
        
        Example: User X likes Post Y → grouped with other likes on Post Y.
        """
        activity_id = str(uuid.uuid4())
        now = time.time()
        group_id = f"{activity_type}:{target_type}:{target_id}"

        # Activity hash fields
        fields = [
            "activity_id", activity_id,
            "type", activity_type,
            "actor_id", actor_id,
            "target_type", target_type,
            "target_id", target_id,
            "created_at", str(now),
        ]
        if metadata:
            fields.extend(["metadata", json.dumps(metadata)])

        group_size = self.r.execute_command(
            "EVAL",
            self.AGGREGATE_ACTIVITY_SCRIPT,
            3,  # KEYS
            f"activity_feed:{user_id}",
            f"activity_group:{user_id}:{group_id}",
            f"activity:{activity_id}",
            activity_id,
            str(now),
            group_id,
            str(20),  # max 20 activities per group
            *fields,
        )
        return group_size

    def get_activity_feed(self, user_id: str, offset: int = 0, limit: int = 20) -> list:
        """
        Get aggregated activity feed.
        Returns groups like: {"type": "like", "target": "post:123", "actors": [...], "count": 5}
        """
        # Get group IDs from feed (sorted by most recent activity)
        group_ids = self.r.zrevrange(
            f"activity_feed:{user_id}", offset, offset + limit - 1, withscores=True
        )

        if not group_ids:
            return []

        feed_items = []
        pipe = self.r.pipeline()

        for group_id, score in group_ids:
            gid = group_id.decode()
            # Get activity IDs in this group (most recent first)
            pipe.lrange(f"activity_group:{user_id}:{gid}", 0, 4)  # Top 5 for display

        group_activities = pipe.execute()

        # Now hydrate each group's activities
        for i, (group_id, score) in enumerate(group_ids):
            gid = group_id.decode()
            activity_ids = group_activities[i]

            if not activity_ids:
                continue

            # Fetch actor details for the group
            inner_pipe = self.r.pipeline()
            for aid in activity_ids:
                inner_pipe.hgetall(f"activity:{aid.decode()}")
            activities = inner_pipe.execute()

            actors = []
            activity_type = None
            target_type = None
            target_id = None

            for activity_data in activities:
                if activity_data:
                    decoded = {k.decode(): v.decode() for k, v in activity_data.items()}
                    actors.append(decoded["actor_id"])
                    activity_type = decoded["type"]
                    target_type = decoded["target_type"]
                    target_id = decoded["target_id"]

            # Get total count in the group
            total_count = self.r.llen(f"activity_group:{user_id}:{gid}")

            feed_items.append({
                "group_id": gid,
                "type": activity_type,
                "target_type": target_type,
                "target_id": target_id,
                "actors": actors[:5],
                "total_actors": total_count,
                "last_activity_at": score,
            })

        return feed_items

    def get_unread_count(self, user_id: str) -> int:
        """Count activities newer than user's last read timestamp."""
        last_read = self.r.get(f"activity_unread:{user_id}")
        if not last_read:
            return self.r.zcard(f"activity_feed:{user_id}")

        return self.r.zcount(
            f"activity_feed:{user_id}",
            f"({last_read.decode()}",
            "+inf",
        )

    def mark_read(self, user_id: str):
        """Mark all activities as read."""
        self.r.set(f"activity_unread:{user_id}", str(time.time()))
```

---

## 5. Real-Time Notification System

```python
class NotificationEngine:
    """
    Multi-channel notification system with delivery tracking.
    
    Channels: in-app, push, email, SMS
    Features: deduplication, rate limiting, preference checking, batching
    
    Data model:
      - notifications:{user_id}          → Sorted Set (notification_ids by time)
      - notification:{id}                → Hash (notification content)
      - notification_prefs:{user_id}     → Hash (channel preferences per type)
      - notification_delivered:{user_id} → Sorted Set (delivered notification tracking)
      - notification_rate:{user_id}:{ch} → String (rate limit counter)
    """

    CHECK_AND_DELIVER_SCRIPT = """
    -- Atomic: check rate limit, check dedup, store notification
    -- KEYS[1] = notifications:{user_id} (sorted set)
    -- KEYS[2] = notification:{id} (hash)
    -- KEYS[3] = notification_rate:{user_id}:{channel}
    -- KEYS[4] = notification_dedup:{user_id}:{dedup_key}
    -- ARGV[1] = notification_id
    -- ARGV[2] = score (timestamp)
    -- ARGV[3] = rate_limit_max
    -- ARGV[4] = rate_limit_window
    -- ARGV[5] = dedup_ttl (0 = no dedup)
    -- ARGV[6..] = notification fields (key-value pairs)
    
    local notif_set = KEYS[1]
    local notif_hash = KEYS[2]
    local rate_key = KEYS[3]
    local dedup_key = KEYS[4]
    local notif_id = ARGV[1]
    local score = ARGV[2]
    local rate_max = tonumber(ARGV[3])
    local rate_window = tonumber(ARGV[4])
    local dedup_ttl = tonumber(ARGV[5])
    
    -- Check deduplication
    if dedup_ttl > 0 then
        if redis.call('EXISTS', dedup_key) == 1 then
            return -1  -- Duplicate
        end
    end
    
    -- Check rate limit
    local current_rate = tonumber(redis.call('GET', rate_key) or '0')
    if current_rate >= rate_max then
        return -2  -- Rate limited
    end
    
    -- Store notification
    for i = 6, #ARGV, 2 do
        redis.call('HSET', notif_hash, ARGV[i], ARGV[i+1])
    end
    redis.call('EXPIRE', notif_hash, 30 * 86400)
    
    -- Add to user's notification set
    redis.call('ZADD', notif_set, score, notif_id)
    
    -- Trim to 1000 notifications max
    local total = redis.call('ZCARD', notif_set)
    if total > 1000 then
        redis.call('ZREMRANGEBYRANK', notif_set, 0, total - 1001)
    end
    
    -- Update rate limit
    if redis.call('EXISTS', rate_key) == 0 then
        redis.call('SET', rate_key, 1, 'EX', rate_window)
    else
        redis.call('INCR', rate_key)
    end
    
    -- Set dedup marker
    if dedup_ttl > 0 then
        redis.call('SET', dedup_key, '1', 'EX', dedup_ttl)
    end
    
    return 1  -- Success
    """

    def __init__(self, r: redis.Redis):
        self.r = r
        self.rate_limits = {
            "in_app": (100, 3600),     # 100 per hour
            "push": (20, 3600),        # 20 per hour
            "email": (5, 3600),        # 5 per hour
            "sms": (3, 86400),         # 3 per day
        }

    def send_notification(
        self,
        user_id: str,
        notif_type: str,
        title: str,
        body: str,
        channel: str = "in_app",
        dedup_key: str = None,
        metadata: dict = None,
    ) -> dict:
        """
        Send a notification with rate limiting and deduplication.
        
        Returns:
          {"status": "delivered", "notification_id": "..."}
          {"status": "deduplicated"} — same notification already sent
          {"status": "rate_limited"} — too many notifications
          {"status": "preference_blocked"} — user disabled this type
        """
        # Check user preferences first (not in Lua for simplicity)
        if not self._check_preference(user_id, notif_type, channel):
            return {"status": "preference_blocked"}

        notif_id = str(uuid.uuid4())
        now = time.time()
        rate_max, rate_window = self.rate_limits.get(channel, (100, 3600))
        dedup_ttl = 3600 if dedup_key else 0  # 1 hour dedup window

        fields = [
            "notification_id", notif_id,
            "type", notif_type,
            "title", title,
            "body", body,
            "channel", channel,
            "created_at", str(now),
            "read", "0",
        ]
        if metadata:
            fields.extend(["metadata", json.dumps(metadata)])

        result = self.r.execute_command(
            "EVAL",
            self.CHECK_AND_DELIVER_SCRIPT,
            4,  # KEYS
            f"notifications:{user_id}",
            f"notification:{notif_id}",
            f"notification_rate:{user_id}:{channel}",
            f"notification_dedup:{user_id}:{dedup_key or notif_id}",
            notif_id,
            str(now),
            str(rate_max),
            str(rate_window),
            str(dedup_ttl),
            *fields,
        )

        if result == -1:
            return {"status": "deduplicated"}
        elif result == -2:
            return {"status": "rate_limited"}

        # Publish real-time event for WebSocket delivery
        self.r.publish(f"notifications:{user_id}", json.dumps({
            "notification_id": notif_id,
            "type": notif_type,
            "title": title,
            "body": body,
            "channel": channel,
            "created_at": now,
        }))

        return {"status": "delivered", "notification_id": notif_id}

    def get_notifications(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 20,
        unread_only: bool = False,
    ) -> list:
        """Retrieve notifications with optional unread filter."""
        notif_ids = self.r.zrevrange(
            f"notifications:{user_id}", offset, offset + limit - 1
        )

        if not notif_ids:
            return []

        pipe = self.r.pipeline()
        for nid in notif_ids:
            pipe.hgetall(f"notification:{nid.decode()}")
        results = pipe.execute()

        notifications = []
        for data in results:
            if data:
                decoded = {k.decode(): v.decode() for k, v in data.items()}
                if unread_only and decoded.get("read") == "1":
                    continue
                notifications.append(decoded)

        return notifications

    def mark_read(self, user_id: str, notification_ids: list = None):
        """Mark specific notifications or all as read."""
        if notification_ids:
            pipe = self.r.pipeline()
            for nid in notification_ids:
                pipe.hset(f"notification:{nid}", "read", "1")
                pipe.hset(f"notification:{nid}", "read_at", str(time.time()))
            pipe.execute()
        else:
            # Mark all as read — get all unread and batch update
            all_ids = self.r.zrevrange(f"notifications:{user_id}", 0, -1)
            pipe = self.r.pipeline()
            for nid in all_ids:
                pipe.hset(f"notification:{nid.decode()}", "read", "1")
            pipe.execute()

    def get_unread_count(self, user_id: str) -> int:
        """Fast unread count using a separate counter (denormalized for speed)."""
        count = self.r.get(f"notification_unread_count:{user_id}")
        if count is not None:
            return int(count)

        # Fallback: count from the set (slower)
        all_ids = self.r.zrevrange(f"notifications:{user_id}", 0, 99)
        pipe = self.r.pipeline()
        for nid in all_ids:
            pipe.hget(f"notification:{nid.decode()}", "read")
        results = pipe.execute()
        unread = sum(1 for r in results if r and r.decode() == "0")

        # Cache the count
        self.r.setex(f"notification_unread_count:{user_id}", 60, unread)
        return unread

    def _check_preference(self, user_id: str, notif_type: str, channel: str) -> bool:
        """Check if user has enabled this notification type for this channel."""
        # Preference format: "type:channel" → "1" (enabled) or "0" (disabled)
        pref = self.r.hget(f"notification_prefs:{user_id}", f"{notif_type}:{channel}")
        if pref is None:
            return True  # Default: enabled
        return pref.decode() == "1"

    def update_preferences(self, user_id: str, preferences: dict):
        """
        Update notification preferences.
        Example: {"like:push": True, "comment:email": False}
        """
        mapping = {k: "1" if v else "0" for k, v in preferences.items()}
        self.r.hset(f"notification_prefs:{user_id}", mapping=mapping)
```

---

## 6. Notification Batching & Digest

```python
class NotificationBatcher:
    """
    Batches rapid-fire notifications into digests.
    
    Instead of: "Alice liked your post", "Bob liked your post", "Carol liked your post"
    Sends: "Alice, Bob, and Carol liked your post"
    
    Uses a time window — if multiple notifications for the same target arrive
    within the window, they're batched into a single delivery.
    
    Data model:
      - notif_batch:{user_id}:{batch_key} → List (pending notification IDs)
      - notif_batch_timer:{user_id}:{bk}  → String (expiry marker for flush timing)
    """

    BATCH_OR_FLUSH_SCRIPT = """
    -- Add to batch. If batch is new, set a timer. If timer expired, signal flush.
    -- KEYS[1] = notif_batch:{user_id}:{batch_key}
    -- KEYS[2] = notif_batch_timer:{user_id}:{batch_key}
    -- ARGV[1] = notification data (JSON)
    -- ARGV[2] = batch_window_seconds
    -- ARGV[3] = max_batch_size
    
    local batch_key = KEYS[1]
    local timer_key = KEYS[2]
    local notif_data = ARGV[1]
    local window = tonumber(ARGV[2])
    local max_size = tonumber(ARGV[3])
    
    -- Add to batch
    redis.call('RPUSH', batch_key, notif_data)
    redis.call('EXPIRE', batch_key, window * 2)
    
    local batch_size = redis.call('LLEN', batch_key)
    
    -- Check if we should flush (max size reached)
    if batch_size >= max_size then
        redis.call('DEL', timer_key)
        return 1  -- Signal: flush now
    end
    
    -- Set timer if this is the first item in batch
    if batch_size == 1 then
        redis.call('SET', timer_key, '1', 'EX', window)
        return 0  -- Signal: timer started, wait
    end
    
    -- Check if timer expired (meaning window elapsed)
    if redis.call('EXISTS', timer_key) == 0 then
        return 1  -- Signal: flush now (window elapsed)
    end
    
    return 0  -- Signal: still accumulating
    """

    def __init__(self, r: redis.Redis, batch_window: int = 30, max_batch_size: int = 10):
        self.r = r
        self.batch_window = batch_window  # seconds to wait before sending digest
        self.max_batch_size = max_batch_size

    def add_to_batch(
        self,
        user_id: str,
        notif_type: str,
        target_id: str,
        actor_id: str,
        content: dict,
    ) -> dict:
        """
        Add a notification to a batch. Returns whether to flush immediately.
        
        Batch key groups notifications by: user + type + target
        Example: all "likes" on the same post are batched together.
        """
        batch_key = f"{notif_type}:{target_id}"
        notif_data = json.dumps({
            "actor_id": actor_id,
            "type": notif_type,
            "target_id": target_id,
            "content": content,
            "timestamp": time.time(),
        })

        should_flush = self.r.execute_command(
            "EVAL",
            self.BATCH_OR_FLUSH_SCRIPT,
            2,
            f"notif_batch:{user_id}:{batch_key}",
            f"notif_batch_timer:{user_id}:{batch_key}",
            notif_data,
            str(self.batch_window),
            str(self.max_batch_size),
        )

        if should_flush:
            return self.flush_batch(user_id, batch_key)

        return {"status": "batching", "batch_key": batch_key}

    def flush_batch(self, user_id: str, batch_key: str) -> dict:
        """
        Flush a batch: collect all items and send as a single digest notification.
        """
        full_key = f"notif_batch:{user_id}:{batch_key}"

        # Atomically get all and delete
        pipe = self.r.pipeline()
        pipe.lrange(full_key, 0, -1)
        pipe.delete(full_key)
        pipe.delete(f"notif_batch_timer:{user_id}:{batch_key}")
        results = pipe.execute()

        items = results[0]
        if not items:
            return {"status": "empty"}

        notifications = [json.loads(item.decode()) for item in items]
        actors = list(set(n["actor_id"] for n in notifications))
        notif_type = notifications[0]["type"]
        target_id = notifications[0]["target_id"]

        # Build digest message
        if len(actors) == 1:
            summary = f"{actors[0]} {notif_type}d your content"
        elif len(actors) == 2:
            summary = f"{actors[0]} and {actors[1]} {notif_type}d your content"
        else:
            summary = f"{actors[0]}, {actors[1]}, and {len(actors) - 2} others {notif_type}d your content"

        return {
            "status": "flushed",
            "summary": summary,
            "actors": actors,
            "count": len(notifications),
            "type": notif_type,
            "target_id": target_id,
        }

    def flush_all_expired(self) -> list:
        """
        Periodic job: find and flush all batches whose timer has expired.
        Run this every 10 seconds via a background worker.
        """
        flushed = []
        cursor = 0

        while True:
            cursor, keys = self.r.scan(
                cursor, match="notif_batch:*", count=100
            )

            for key in keys:
                key_str = key.decode()
                # Extract user_id and batch_key from "notif_batch:{user_id}:{batch_key}"
                parts = key_str.split(":", 2)
                if len(parts) < 3:
                    continue

                user_id = parts[1]
                batch_key = parts[2]

                # Check if timer expired
                timer_key = f"notif_batch_timer:{user_id}:{batch_key}"
                if not self.r.exists(timer_key):
                    # Timer expired — flush
                    result = self.flush_batch(user_id, batch_key)
                    if result["status"] == "flushed":
                        flushed.append(result)

            if cursor == 0:
                break

        return flushed
```

---

## 7. Real-Time Feed Updates with Streams

```python
class RealTimeFeedStream:
    """
    Uses Redis Streams for real-time feed updates via Server-Sent Events (SSE)
    or WebSockets.
    
    When a new post appears in a user's timeline, we also write to a per-user
    stream. Connected clients consume this stream to get instant updates.
    
    Data model:
      - feed_stream:{user_id}   → Stream (real-time feed events)
      - feed_consumers:{user_id} → Set (active consumer IDs for cleanup)
    """

    def __init__(self, r: redis.Redis, max_stream_length: int = 1000):
        self.r = r
        self.max_stream_length = max_stream_length

    def publish_feed_event(self, user_id: str, event_type: str, payload: dict):
        """
        Publish a real-time event to a user's feed stream.
        Called after fanout writes to the timeline sorted set.
        """
        stream_key = f"feed_stream:{user_id}"

        fields = {
            "event_type": event_type,
            "payload": json.dumps(payload),
            "timestamp": str(time.time()),
        }

        # XADD with MAXLEN to prevent unbounded growth
        self.r.xadd(stream_key, fields, maxlen=self.max_stream_length, approximate=True)

    def subscribe_feed(self, user_id: str, last_id: str = "$", timeout_ms: int = 30000):
        """
        Block-read from a user's feed stream.
        
        This is called in a loop by the WebSocket/SSE handler:
        1. Client connects, sends last known event ID (or "$" for new events only)
        2. Server calls subscribe_feed() which blocks until new events arrive
        3. Server pushes events to client
        4. Repeat
        
        Returns list of (event_id, event_data) tuples.
        """
        stream_key = f"feed_stream:{user_id}"

        # XREAD with BLOCK — waits for new events
        result = self.r.xread(
            {stream_key: last_id},
            count=10,
            block=timeout_ms,
        )

        if not result:
            return []  # Timeout, no new events

        events = []
        for stream_name, messages in result:
            for msg_id, fields in messages:
                event_id = msg_id.decode()
                event_data = {k.decode(): v.decode() for k, v in fields.items()}
                event_data["payload"] = json.loads(event_data["payload"])
                events.append((event_id, event_data))

        return events

    def get_missed_events(self, user_id: str, since_id: str, limit: int = 50) -> list:
        """
        When a client reconnects, fetch events they missed while disconnected.
        """
        stream_key = f"feed_stream:{user_id}"

        # XRANGE from their last known ID to latest
        result = self.r.xrange(stream_key, min=f"({since_id}", count=limit)

        events = []
        for msg_id, fields in result:
            event_data = {k.decode(): v.decode() for k, v in fields.items()}
            event_data["payload"] = json.loads(event_data["payload"])
            events.append((msg_id.decode(), event_data))

        return events

    def fanout_with_realtime(self, post: Post, follower_ids: list):
        """
        Combined fanout: write to timeline sorted set + publish stream event.
        """
        pipe = self.r.pipeline()

        for follower_id in follower_ids:
            # Push to timeline (sorted set for pagination)
            pipe.zadd(f"timeline:{follower_id}", {post.post_id: post.created_at})

        pipe.execute()

        # Publish real-time events (separate from pipeline for stream semantics)
        event_payload = {
            "post_id": post.post_id,
            "author_id": post.author_id,
            "content": post.content,
            "created_at": post.created_at,
        }

        for follower_id in follower_ids:
            self.publish_feed_event(follower_id, "new_post", event_payload)
```

---

## 8. Feed Ranking & Scoring

```python
class RankedFeedEngine:
    """
    Scored/ranked feed that combines recency with engagement signals.
    
    Instead of purely chronological, each post gets a composite score:
      score = recency_weight * time_decay + engagement_weight * engagement_score
    
    Engagement signals: likes, comments, shares, view duration
    Recency: exponential decay from post creation time
    
    Data model:
      - ranked_feed:{user_id}      → Sorted Set (post_id scored by composite rank)
      - post_engagement:{post_id}  → Hash (like_count, comment_count, share_count, view_count)
      - user_affinity:{u1}:{u2}    → String (interaction score between users)
    """

    RECALCULATE_SCORE_SCRIPT = """
    -- Recalculate a post's score in a user's feed based on engagement + recency + affinity
    -- KEYS[1] = ranked_feed:{user_id}
    -- KEYS[2] = post_engagement:{post_id}
    -- KEYS[3] = user_affinity:{user_id}:{author_id}
    -- ARGV[1] = post_id
    -- ARGV[2] = post_created_at (unix timestamp)
    -- ARGV[3] = current_time (unix timestamp)
    -- ARGV[4] = recency_half_life (seconds — how fast time decay happens)
    
    local feed_key = KEYS[1]
    local engagement_key = KEYS[2]
    local affinity_key = KEYS[3]
    local post_id = ARGV[1]
    local created_at = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    local half_life = tonumber(ARGV[4])
    
    -- Recency: exponential decay
    local age_seconds = now - created_at
    local recency_score = math.exp(-0.693 * age_seconds / half_life)  -- ln(2) ≈ 0.693
    
    -- Engagement: weighted sum of signals
    local likes = tonumber(redis.call('HGET', engagement_key, 'likes') or '0')
    local comments = tonumber(redis.call('HGET', engagement_key, 'comments') or '0')
    local shares = tonumber(redis.call('HGET', engagement_key, 'shares') or '0')
    local engagement_score = likes * 1 + comments * 3 + shares * 5
    -- Normalize engagement to 0-1 range (sigmoid)
    local norm_engagement = engagement_score / (engagement_score + 50)
    
    -- Affinity: how much this user interacts with the author
    local affinity = tonumber(redis.call('GET', affinity_key) or '0.5')
    
    -- Composite score (weights tunable)
    local final_score = 0.4 * recency_score + 0.35 * norm_engagement + 0.25 * affinity
    
    -- Update in the sorted set
    redis.call('ZADD', feed_key, final_score, post_id)
    
    return tostring(final_score)
    """

    def __init__(self, r: redis.Redis, recency_half_life: int = 21600):
        self.r = r
        self.recency_half_life = recency_half_life  # 6 hours default

    def score_post_for_user(self, user_id: str, post_id: str, author_id: str) -> float:
        """Recalculate a post's rank score for a specific user."""
        created_at = self.r.hget(f"post:{post_id}", "created_at")
        if not created_at:
            return 0.0

        score = self.r.execute_command(
            "EVAL",
            self.RECALCULATE_SCORE_SCRIPT,
            3,
            f"ranked_feed:{user_id}",
            f"post_engagement:{post_id}",
            f"user_affinity:{user_id}:{author_id}",
            post_id,
            created_at.decode(),
            str(time.time()),
            str(self.recency_half_life),
        )
        return float(score)

    def record_engagement(self, post_id: str, signal_type: str):
        """
        Record an engagement signal and trigger re-scoring for affected feeds.
        
        signal_type: "likes", "comments", "shares", "views"
        """
        self.r.hincrby(f"post_engagement:{post_id}", signal_type, 1)

    def record_affinity(self, user_id: str, target_user_id: str, interaction_weight: float = 0.1):
        """
        Update affinity score when user interacts with another user's content.
        Uses exponential moving average.
        """
        key = f"user_affinity:{user_id}:{target_user_id}"
        current = float(self.r.get(key) or 0.5)
        # EMA: new_value = alpha * signal + (1 - alpha) * old_value
        alpha = 0.1
        new_value = alpha * min(1.0, current + interaction_weight) + (1 - alpha) * current
        self.r.setex(key, 30 * 86400, str(min(1.0, new_value)))

    def get_ranked_feed(self, user_id: str, offset: int = 0, limit: int = 20) -> list:
        """Get feed sorted by composite rank score (highest first)."""
        post_ids = self.r.zrevrange(
            f"ranked_feed:{user_id}", offset, offset + limit - 1, withscores=True
        )

        if not post_ids:
            return []

        pipe = self.r.pipeline()
        for post_id, score in post_ids:
            pipe.hgetall(f"post:{post_id.decode()}")
        results = pipe.execute()

        posts = []
        for i, data in enumerate(results):
            if data:
                decoded = {k.decode(): v.decode() for k, v in data.items()}
                decoded["rank_score"] = post_ids[i][1]
                posts.append(decoded)

        return posts

    def refresh_feed_scores(self, user_id: str, batch_size: int = 50):
        """
        Background job: re-score all posts in a user's feed.
        Run periodically or on feed load if stale.
        """
        post_ids = self.r.zrange(f"ranked_feed:{user_id}", 0, batch_size - 1)

        for post_id in post_ids:
            pid = post_id.decode()
            author_id = self.r.hget(f"post:{pid}", "author_id")
            if author_id:
                self.score_post_for_user(user_id, pid, author_id.decode())
```

---

## 9. Follow/Unfollow with Consistency

```python
class SocialGraphEngine:
    """
    Manages follow relationships with consistency guarantees.
    
    Challenges:
    - Follow/unfollow must atomically update both sides (followers + following)
    - Follower counts must stay accurate (used for celebrity detection)
    - Follow events trigger timeline backfill/cleanup
    
    Data model:
      - followers:{user_id}   → Set (who follows this user)
      - following:{user_id}   → Set (who this user follows)
      - user_meta:{user_id}   → Hash (follower_count, following_count)
      - follow_events         → Stream (for async processing: backfill, notifications)
    """

    ATOMIC_FOLLOW_SCRIPT = """
    -- Atomic follow: update both sides + counts + emit event
    -- KEYS[1] = following:{follower}
    -- KEYS[2] = followers:{followee}
    -- KEYS[3] = user_meta:{followee}
    -- KEYS[4] = user_meta:{follower}
    -- KEYS[5] = follow_events (stream)
    -- ARGV[1] = followee_id
    -- ARGV[2] = follower_id
    -- ARGV[3] = timestamp
    
    local following_key = KEYS[1]
    local followers_key = KEYS[2]
    local followee_meta = KEYS[3]
    local follower_meta = KEYS[4]
    local events_stream = KEYS[5]
    local followee_id = ARGV[1]
    local follower_id = ARGV[2]
    local timestamp = ARGV[3]
    
    -- Check if already following
    if redis.call('SISMEMBER', following_key, followee_id) == 1 then
        return 0  -- Already following
    end
    
    -- Add to both sets
    redis.call('SADD', following_key, followee_id)
    redis.call('SADD', followers_key, follower_id)
    
    -- Update counts
    redis.call('HINCRBY', followee_meta, 'follower_count', 1)
    redis.call('HINCRBY', follower_meta, 'following_count', 1)
    
    -- Emit follow event for async processing
    redis.call('XADD', events_stream, 'MAXLEN', '~', '10000', '*',
        'type', 'follow',
        'follower_id', follower_id,
        'followee_id', followee_id,
        'timestamp', timestamp)
    
    return 1  -- Success
    """

    ATOMIC_UNFOLLOW_SCRIPT = """
    -- Atomic unfollow: reverse of follow
    -- KEYS/ARGV same structure as follow
    
    local following_key = KEYS[1]
    local followers_key = KEYS[2]
    local followee_meta = KEYS[3]
    local follower_meta = KEYS[4]
    local events_stream = KEYS[5]
    local followee_id = ARGV[1]
    local follower_id = ARGV[2]
    local timestamp = ARGV[3]
    
    -- Check if actually following
    if redis.call('SISMEMBER', following_key, followee_id) == 0 then
        return 0  -- Not following
    end
    
    -- Remove from both sets
    redis.call('SREM', following_key, followee_id)
    redis.call('SREM', followers_key, follower_id)
    
    -- Update counts
    redis.call('HINCRBY', followee_meta, 'follower_count', -1)
    redis.call('HINCRBY', follower_meta, 'following_count', -1)
    
    -- Emit unfollow event
    redis.call('XADD', events_stream, 'MAXLEN', '~', '10000', '*',
        'type', 'unfollow',
        'follower_id', follower_id,
        'followee_id', followee_id,
        'timestamp', timestamp)
    
    return 1  -- Success
    """

    def __init__(self, r: redis.Redis):
        self.r = r

    def follow(self, follower_id: str, followee_id: str) -> bool:
        """Atomically follow a user."""
        result = self.r.execute_command(
            "EVAL",
            self.ATOMIC_FOLLOW_SCRIPT,
            5,
            f"following:{follower_id}",
            f"followers:{followee_id}",
            f"user_meta:{followee_id}",
            f"user_meta:{follower_id}",
            "follow_events",
            followee_id,
            follower_id,
            str(time.time()),
        )
        return result == 1

    def unfollow(self, follower_id: str, followee_id: str) -> bool:
        """Atomically unfollow a user."""
        result = self.r.execute_command(
            "EVAL",
            self.ATOMIC_UNFOLLOW_SCRIPT,
            5,
            f"following:{follower_id}",
            f"followers:{followee_id}",
            f"user_meta:{followee_id}",
            f"user_meta:{follower_id}",
            "follow_events",
            followee_id,
            follower_id,
            str(time.time()),
        )
        return result == 1

    def get_follower_count(self, user_id: str) -> int:
        count = self.r.hget(f"user_meta:{user_id}", "follower_count")
        return int(count) if count else 0

    def get_mutual_followers(self, user_a: str, user_b: str) -> set:
        """Users who follow both A and B."""
        return self.r.sinter(f"followers:{user_a}", f"followers:{user_b}")

    def get_suggestions(self, user_id: str, limit: int = 10) -> list:
        """
        Friend-of-friend suggestions: users followed by people you follow,
        that you don't already follow.
        """
        following = self.r.smembers(f"following:{user_id}")
        if not following:
            return []

        # Get who your friends follow (sample for performance)
        candidates = {}
        sample = list(following)[:20]  # Limit to 20 friends for speed

        for friend_id in sample:
            friend_following = self.r.srandmember(
                f"following:{friend_id.decode()}", 10
            )
            if friend_following:
                for candidate in friend_following:
                    cid = candidate.decode()
                    if cid != user_id and candidate not in following:
                        candidates[cid] = candidates.get(cid, 0) + 1

        # Sort by frequency (most mutual connections first)
        sorted_candidates = sorted(candidates.items(), key=lambda x: x[1], reverse=True)
        return [{"user_id": uid, "mutual_count": count} for uid, count in sorted_candidates[:limit]]
```

---

## 10. Push Notification Delivery Pipeline

```python
class PushNotificationPipeline:
    """
    Reliable push notification delivery using Redis Streams as a work queue.
    
    Architecture:
      Producer → Redis Stream → Consumer Group → Push Provider (APNs/FCM)
    
    Features:
    - At-least-once delivery via consumer groups
    - Dead letter queue for permanently failed notifications
    - Device token management
    - Per-device rate limiting
    
    Data model:
      - push_queue             → Stream (pending push notifications)
      - push_dlq              → Stream (dead letter queue)
      - push_tokens:{user_id} → Set (device tokens for a user)
      - push_delivered:{id}   → String (delivery confirmation, short TTL)
    """

    def __init__(self, r: redis.Redis, consumer_group: str = "push_workers"):
        self.r = r
        self.consumer_group = consumer_group
        self._ensure_consumer_group()

    def _ensure_consumer_group(self):
        try:
            self.r.xgroup_create("push_queue", self.consumer_group, id="0", mkstream=True)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    def enqueue_push(self, user_id: str, title: str, body: str, data: dict = None):
        """
        Enqueue a push notification for delivery.
        One stream entry per user — the worker resolves device tokens at delivery time.
        """
        self.r.xadd("push_queue", {
            "user_id": user_id,
            "title": title,
            "body": body,
            "data": json.dumps(data or {}),
            "enqueued_at": str(time.time()),
            "attempts": "0",
        }, maxlen=100000, approximate=True)

    def process_batch(self, consumer_id: str, batch_size: int = 10, block_ms: int = 5000) -> list:
        """
        Consumer worker: claim and process a batch of push notifications.
        """
        # Read new messages from the stream
        messages = self.r.xreadgroup(
            self.consumer_group,
            consumer_id,
            {"push_queue": ">"},
            count=batch_size,
            block=block_ms,
        )

        if not messages:
            return []

        results = []
        for stream_name, entries in messages:
            for msg_id, fields in entries:
                decoded = {k.decode(): v.decode() for k, v in fields.items()}
                delivery_result = self._deliver_push(msg_id, decoded)
                results.append(delivery_result)

        return results

    def _deliver_push(self, msg_id: bytes, notification: dict) -> dict:
        """Attempt to deliver a push notification to all user's devices."""
        user_id = notification["user_id"]
        attempts = int(notification["attempts"])

        # Get device tokens
        tokens = self.r.smembers(f"push_tokens:{user_id}")
        if not tokens:
            # No devices registered — ACK and skip
            self.r.xack("push_queue", self.consumer_group, msg_id)
            return {"status": "no_devices", "user_id": user_id}

        # Simulate delivery to push provider (APNs/FCM)
        delivered_to = []
        failed_tokens = []

        for token in tokens:
            token_str = token.decode()
            success = self._send_to_provider(token_str, notification)
            if success:
                delivered_to.append(token_str)
            else:
                failed_tokens.append(token_str)

        if delivered_to:
            # At least one device received it — ACK
            self.r.xack("push_queue", self.consumer_group, msg_id)
            # Record delivery
            self.r.setex(
                f"push_delivered:{msg_id.decode()}",
                86400,
                json.dumps({"delivered_to": delivered_to, "time": time.time()}),
            )
            return {"status": "delivered", "devices": len(delivered_to)}

        # All devices failed
        if attempts >= 3:
            # Move to DLQ
            self.r.xadd("push_dlq", {
                **notification,
                "original_msg_id": msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
                "failure_reason": "max_retries_exceeded",
                "failed_at": str(time.time()),
            })
            self.r.xack("push_queue", self.consumer_group, msg_id)
            return {"status": "dead_lettered", "user_id": user_id}

        # Will be retried via pending entries (XPENDING + XCLAIM)
        return {"status": "retry_pending", "attempts": attempts}

    def _send_to_provider(self, device_token: str, notification: dict) -> bool:
        """Placeholder for actual APNs/FCM call."""
        # In production: call Apple/Google push API
        return True

    def register_device(self, user_id: str, device_token: str, platform: str):
        """Register a device token for push notifications."""
        self.r.sadd(f"push_tokens:{user_id}", device_token)
        self.r.hset(f"push_device:{device_token}", mapping={
            "user_id": user_id,
            "platform": platform,
            "registered_at": str(time.time()),
        })

    def unregister_device(self, user_id: str, device_token: str):
        """Remove a device token (user logged out, token expired)."""
        self.r.srem(f"push_tokens:{user_id}", device_token)
        self.r.delete(f"push_device:{device_token}")

    def reclaim_stale(self, consumer_id: str, min_idle_ms: int = 60000) -> int:
        """
        Reclaim messages from dead consumers.
        If a consumer crashes, its pending messages become stale — we reclaim them.
        """
        # Get pending messages older than min_idle_ms
        pending = self.r.xpending_range(
            "push_queue", self.consumer_group, min="-", max="+", count=100
        )

        reclaimed = 0
        for entry in pending:
            if entry["time_since_delivered"] > min_idle_ms:
                # Claim the message
                claimed = self.r.xclaim(
                    "push_queue",
                    self.consumer_group,
                    consumer_id,
                    min_idle_time=min_idle_ms,
                    message_ids=[entry["message_id"]],
                )
                reclaimed += len(claimed)

        return reclaimed
```

---

## 11. Feed Pagination Patterns

```python
class FeedPaginator:
    """
    Production pagination strategies for feeds.
    
    Offset pagination (page 1, 2, 3) is broken for feeds because new items
    shift the window, causing duplicates or skips.
    
    Cursor-based pagination solves this:
    - Score cursor: "give me items older than this timestamp"
    - ID cursor: "give me items after this specific post"
    """

    def __init__(self, r: redis.Redis):
        self.r = r

    def paginate_by_score(
        self,
        user_id: str,
        max_score: float = None,
        limit: int = 20,
    ) -> dict:
        """
        Score-based cursor pagination (recommended for timelines).
        
        Client passes max_score from previous page's last item.
        First request: max_score=None (starts from newest).
        """
        timeline_key = f"timeline:{user_id}"

        if max_score is None:
            max_score = "+inf"
        else:
            # Exclusive upper bound: items strictly older than cursor
            max_score = f"({max_score}"

        # Fetch limit+1 to know if there are more pages
        results = self.r.zrevrangebyscore(
            timeline_key,
            max_score,
            "-inf",
            start=0,
            num=limit + 1,
            withscores=True,
        )

        has_more = len(results) > limit
        items = results[:limit]

        # Next cursor is the score of the last item
        next_cursor = None
        if has_more and items:
            next_cursor = items[-1][1]  # Score of last item

        return {
            "items": [(pid.decode(), score) for pid, score in items],
            "next_cursor": next_cursor,
            "has_more": has_more,
        }

    def paginate_by_rank(
        self,
        user_id: str,
        cursor_score: float = None,
        cursor_id: str = None,
        limit: int = 20,
    ) -> dict:
        """
        For ranked feeds where scores aren't unique timestamps.
        Uses (score, id) pair as cursor to handle ties.
        """
        feed_key = f"ranked_feed:{user_id}"

        if cursor_score is None:
            # First page: get top items
            results = self.r.zrevrange(feed_key, 0, limit, withscores=True)
        else:
            # Get items with score <= cursor_score
            results = self.r.zrevrangebyscore(
                feed_key,
                f"({cursor_score}" if cursor_id else cursor_score,
                "-inf",
                start=0,
                num=limit + 1,
                withscores=True,
            )

        # Handle score ties by skipping until we pass the cursor_id
        if cursor_id and results:
            filtered = []
            past_cursor = False
            for pid, score in results:
                if pid.decode() == cursor_id:
                    past_cursor = True
                    continue
                if past_cursor or score < (cursor_score or float("inf")):
                    filtered.append((pid, score))
            results = filtered

        has_more = len(results) > limit
        items = results[:limit]

        next_cursor = None
        if has_more and items:
            last_pid, last_score = items[-1]
            next_cursor = {"score": last_score, "id": last_pid.decode()}

        return {
            "items": [(pid.decode(), score) for pid, score in items],
            "next_cursor": next_cursor,
            "has_more": has_more,
        }

    def infinite_scroll_state(self, user_id: str, session_id: str) -> dict:
        """
        Track infinite scroll position per session.
        Allows resuming scroll position across app restarts.
        """
        state_key = f"scroll_state:{user_id}:{session_id}"
        state = self.r.hgetall(state_key)

        if state:
            return {k.decode(): v.decode() for k, v in state.items()}
        return {"cursor": None, "items_seen": "0"}

    def save_scroll_state(self, user_id: str, session_id: str, cursor: str, items_seen: int):
        """Save scroll position for session resume."""
        state_key = f"scroll_state:{user_id}:{session_id}"
        self.r.hset(state_key, mapping={
            "cursor": cursor,
            "items_seen": str(items_seen),
            "updated_at": str(time.time()),
        })
        self.r.expire(state_key, 86400)  # 24h TTL
```

---

## 12. Production Considerations

### Memory Estimation

| Component | Per-User Cost | 1M Users |
|-----------|--------------|----------|
| Timeline (800 posts, sorted set) | ~50 KB | ~50 GB |
| Notification set (200 items) | ~15 KB | ~15 GB |
| Activity feed (500 groups) | ~35 KB | ~35 GB |
| Follower/following sets (avg 200) | ~8 KB | ~8 GB |
| Feed streams (1000 events) | ~80 KB | ~80 GB |

### Scaling Strategies

| Challenge | Solution |
|-----------|----------|
| Celebrity fanout too slow | Hybrid model — pull for celebrities |
| Timeline sorted set too large | Trim to 800 items; older posts fall off |
| Memory per user too high | Shard by user_id hash across Redis Cluster nodes |
| Fanout latency spikes | Async fanout via Redis Streams + worker pool |
| Feed assembly too slow (pull) | Short-lived cache (60s) of assembled feed |
| Global ordering across shards | Use timestamp + user_id composite for tie-breaking |

### Decision Matrix: Push vs Pull vs Hybrid

| Factor | Fan-Out on Write (Push) | Fan-Out on Read (Pull) | Hybrid |
|--------|------------------------|----------------------|--------|
| Read latency | O(1) page fetch | O(N) merge N followed users | O(1) + O(K) for K celebrities |
| Write latency | O(F) for F followers | O(1) | O(F) for normal, O(1) for celebrities |
| Memory usage | High (duplicated across timelines) | Low (stored once per author) | Medium |
| Celebrity handling | Problematic (millions of writes) | Natural (just another source) | Optimal (routed correctly) |
| Delete/edit propagation | Expensive (remove from all timelines) | Free (single source of truth) | Expensive for normal users |
| Best for | < 10K followers, latency-critical reads | > 100K followers, write-heavy | Production systems at scale |

### Async Fanout Architecture

```
┌─────────┐     ┌───────────────┐     ┌─────────────────┐     ┌─────────────┐
│  User   │────▶│  API Server   │────▶│  Redis Stream    │────▶│  Fanout     │
│  Posts  │     │  (validates)  │     │  (work queue)   │     │  Workers    │
└─────────┘     └───────────────┘     └─────────────────┘     └──────┬──────┘
                                                                      │
                       ┌──────────────────────────────────────────────┘
                       ▼
              ┌─────────────────┐     ┌─────────────────┐
              │  Timeline       │     │  Feed Stream     │
              │  Sorted Sets    │     │  (real-time)     │
              │  (pagination)   │     │  (WebSocket/SSE) │
              └─────────────────┘     └─────────────────┘
```

### Consistency Guarantees

- **Timeline writes:** Eventually consistent (async fanout, 50-500ms delay acceptable)
- **Follower counts:** Strongly consistent (Lua atomic increment/decrement)
- **Notification delivery:** At-least-once (Stream consumer groups with ACK)
- **Feed ordering:** Consistent within a single user's view (sorted set guarantees)
- **Delete propagation:** Best-effort with background cleanup job for stragglers

### Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Fanout worker crash | Some followers don't get the post | Stream consumer group: unACKed messages reclaimed by other workers |
| Redis primary failover | Brief write interruption | Sentinel/Cluster with `WAIT` for critical writes; accept brief staleness for feeds |
| Timeline sorted set corrupted | User sees wrong feed | Rebuild from author's post lists (pull-model fallback) |
| Celebrity threshold miscounted | Wrong fanout strategy | Periodic reconciliation job; SCARD vs stored count |
| Stream consumer lag | Real-time events delayed | Monitor `XPENDING`; auto-scale workers on lag growth |
