# Schema Design - Social Media & Communication (Problems 71-90)

## Staff Architect Level - Database Schema Design

---

## Problem 71: Design a Twitter/X-like Social Feed System

**Difficulty:** Expert | **Frequency:** Very High (FAANG interviews)

**Requirements:**
- Users post tweets (280 chars)
- Follow/unfollow
- Home timeline (feed of people you follow)
- Likes, retweets, replies
- Hashtags and mentions

```sql
-- Users
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    username VARCHAR(30) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    bio VARCHAR(500),
    avatar_url VARCHAR(500),
    follower_count INT DEFAULT 0,  -- Denormalized
    following_count INT DEFAULT 0,
    tweet_count INT DEFAULT 0,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_username (username)
);

-- Follow relationships
CREATE TABLE follows (
    follower_id UUID NOT NULL REFERENCES users(user_id),
    following_id UUID NOT NULL REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (follower_id, following_id),
    INDEX idx_following (following_id, follower_id)  -- For "followers of X"
);

-- Tweets
CREATE TABLE tweets (
    tweet_id BIGINT PRIMARY KEY,  -- Snowflake ID (time-ordered)
    user_id UUID NOT NULL REFERENCES users(user_id),
    content VARCHAR(280) NOT NULL,
    tweet_type ENUM('original', 'reply', 'retweet', 'quote') DEFAULT 'original',
    reply_to_tweet_id BIGINT REFERENCES tweets(tweet_id),
    retweet_of_id BIGINT REFERENCES tweets(tweet_id),
    quote_of_id BIGINT REFERENCES tweets(tweet_id),
    like_count INT DEFAULT 0,
    retweet_count INT DEFAULT 0,
    reply_count INT DEFAULT 0,
    view_count BIGINT DEFAULT 0,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_user_time (user_id, created_at DESC),
    INDEX idx_reply (reply_to_tweet_id),
    INDEX idx_created (created_at DESC)
);

-- Likes
CREATE TABLE tweet_likes (
    user_id UUID NOT NULL,
    tweet_id BIGINT NOT NULL REFERENCES tweets(tweet_id),
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, tweet_id),
    INDEX idx_tweet (tweet_id)  -- "Who liked this tweet"
);

-- Hashtags
CREATE TABLE hashtags (
    hashtag_id INT PRIMARY KEY AUTO_INCREMENT,
    tag VARCHAR(100) UNIQUE NOT NULL,
    tweet_count BIGINT DEFAULT 0,
    INDEX idx_tag (tag)
);

CREATE TABLE tweet_hashtags (
    tweet_id BIGINT NOT NULL REFERENCES tweets(tweet_id),
    hashtag_id INT NOT NULL REFERENCES hashtags(hashtag_id),
    PRIMARY KEY (tweet_id, hashtag_id),
    INDEX idx_hashtag_time (hashtag_id, tweet_id DESC)
);

-- Mentions
CREATE TABLE tweet_mentions (
    tweet_id BIGINT NOT NULL,
    mentioned_user_id UUID NOT NULL,
    PRIMARY KEY (tweet_id, mentioned_user_id),
    INDEX idx_mentioned (mentioned_user_id, tweet_id DESC)
);
```

**Home Timeline Query (Fan-out on read approach):**
```sql
-- Simple: Get latest tweets from people I follow
SELECT t.tweet_id, t.content, t.created_at, u.username, u.display_name
FROM tweets t
JOIN follows f ON t.user_id = f.following_id
JOIN users u ON t.user_id = u.user_id
WHERE f.follower_id = @current_user_id
  AND t.is_deleted = FALSE
ORDER BY t.created_at DESC
LIMIT 20;
```

**Architect Discussion - Timeline Architecture:**

| Approach | How it Works | Pros | Cons |
|----------|-------------|------|------|
| Fan-out on Read | Query follows + join tweets at read time | Simple, always fresh | Slow for users following 1000+ people |
| Fan-out on Write | Push tweet to all followers' timelines on write | Fast reads | Celebrity problem (millions of writes per tweet) |
| Hybrid (Twitter's actual approach) | Fan-out on write for normal users, fan-out on read for celebrities | Balanced | Complex |

**Fan-out on Write (Redis-backed):**
```
On tweet creation:
1. Get all follower_ids of author
2. For each follower: LPUSH timeline:{follower_id} tweet_id
3. LTRIM to keep last 800 tweets
4. For celebrities (>500K followers): Skip fan-out, merge at read time
```

---

## Problem 72: Design a Direct Messaging System

**Difficulty:** Hard | **Frequency:** Very High

**Requirements:**
- 1:1 and group conversations
- Message delivery receipts (sent, delivered, read)
- Message types (text, image, file)
- Online/typing indicators

```sql
-- Conversations (both 1:1 and groups)
CREATE TABLE conversations (
    conversation_id UUID PRIMARY KEY,
    type ENUM('direct', 'group') NOT NULL,
    name VARCHAR(255),  -- NULL for direct messages
    created_by UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()  -- Last message time (for sorting)
);

-- Participants
CREATE TABLE conversation_participants (
    conversation_id UUID NOT NULL REFERENCES conversations(conversation_id),
    user_id UUID NOT NULL,
    role ENUM('member', 'admin', 'owner') DEFAULT 'member',
    joined_at TIMESTAMP DEFAULT NOW(),
    left_at TIMESTAMP,  -- NULL = still active
    last_read_message_id BIGINT,  -- For unread count
    is_muted BOOLEAN DEFAULT FALSE,
    notification_level ENUM('all', 'mentions', 'none') DEFAULT 'all',
    PRIMARY KEY (conversation_id, user_id),
    INDEX idx_user (user_id, left_at)
);

-- Messages
CREATE TABLE messages (
    message_id BIGINT PRIMARY KEY,  -- Snowflake ID
    conversation_id UUID NOT NULL REFERENCES conversations(conversation_id),
    sender_id UUID NOT NULL,
    message_type ENUM('text', 'image', 'file', 'audio', 'video', 'system') DEFAULT 'text',
    content TEXT,
    metadata JSONB,  -- File info, image dimensions, etc.
    reply_to_message_id BIGINT,
    is_edited BOOLEAN DEFAULT FALSE,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    edited_at TIMESTAMP,
    INDEX idx_conversation_time (conversation_id, created_at DESC),
    INDEX idx_sender (sender_id)
);

-- Delivery receipts
CREATE TABLE message_receipts (
    message_id BIGINT NOT NULL REFERENCES messages(message_id),
    user_id UUID NOT NULL,
    delivered_at TIMESTAMP,
    read_at TIMESTAMP,
    PRIMARY KEY (message_id, user_id),
    INDEX idx_user_unread (user_id, read_at)
);
```

**Get Conversations with Unread Count:**
```sql
SELECT c.conversation_id, c.type, c.name, c.updated_at,
       m.content AS last_message,
       m.sender_id AS last_sender,
       m.created_at AS last_message_time,
       (SELECT COUNT(*) 
        FROM messages msg 
        WHERE msg.conversation_id = c.conversation_id 
          AND msg.message_id > COALESCE(cp.last_read_message_id, 0)
          AND msg.sender_id != @current_user_id
       ) AS unread_count
FROM conversations c
JOIN conversation_participants cp ON c.conversation_id = cp.conversation_id
LEFT JOIN LATERAL (
    SELECT content, sender_id, created_at
    FROM messages
    WHERE conversation_id = c.conversation_id
    ORDER BY created_at DESC
    LIMIT 1
) m ON TRUE
WHERE cp.user_id = @current_user_id
  AND cp.left_at IS NULL
ORDER BY c.updated_at DESC
LIMIT 50;
```

**Architect Discussion:**
- Messages are typically stored in **Cassandra** (partition by conversation_id, cluster by time)
- Real-time delivery: **WebSockets** with connection server routing
- Read receipts: Batch update, don't write per-message for groups > 100
- For 1:1: Create composite key `LEAST(user1,user2) || GREATEST(user1,user2)` to deduplicate

---

## Problem 73: Design a Notification System

**Difficulty:** Hard | **Frequency:** Very High

```sql
CREATE TABLE notifications (
    notification_id BIGINT PRIMARY KEY,  -- Snowflake ID
    user_id UUID NOT NULL,  -- Recipient
    type VARCHAR(50) NOT NULL,  -- 'like', 'comment', 'follow', 'mention', 'system'
    title VARCHAR(255),
    body TEXT,
    
    -- Actor (who triggered this)
    actor_id UUID,  -- The user who did the action
    
    -- Target (what was acted upon)
    target_type VARCHAR(50),  -- 'tweet', 'comment', 'post'
    target_id VARCHAR(100),
    
    -- Grouping (collapse similar notifications)
    group_key VARCHAR(255),  -- e.g., "like:tweet:12345" to group all likes on same tweet
    
    -- Status
    is_read BOOLEAN DEFAULT FALSE,
    is_seen BOOLEAN DEFAULT FALSE,  -- Seen in notification bell
    read_at TIMESTAMP,
    
    -- Delivery
    channels JSONB DEFAULT '["in_app"]',  -- ["in_app", "push", "email"]
    push_sent_at TIMESTAMP,
    email_sent_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    
    INDEX idx_user_unread (user_id, is_read, created_at DESC),
    INDEX idx_user_time (user_id, created_at DESC),
    INDEX idx_group (user_id, group_key, created_at DESC)
);

-- Notification preferences
CREATE TABLE notification_preferences (
    user_id UUID NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    channel VARCHAR(20) NOT NULL,  -- 'in_app', 'push', 'email', 'sms'
    is_enabled BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (user_id, notification_type, channel)
);
```

**Grouped Notifications Query (e.g., "John and 5 others liked your tweet"):**
```sql
WITH grouped AS (
    SELECT group_key,
           user_id,
           type,
           target_type,
           target_id,
           MAX(created_at) AS latest_at,
           COUNT(*) AS count,
           ARRAY_AGG(actor_id ORDER BY created_at DESC) AS actor_ids
    FROM notifications
    WHERE user_id = @current_user_id
      AND group_key IS NOT NULL
      AND created_at > NOW() - INTERVAL '7 days'
    GROUP BY group_key, user_id, type, target_type, target_id
),
ungrouped AS (
    SELECT notification_id, user_id, type, actor_id, target_type, target_id,
           created_at AS latest_at, 1 AS count
    FROM notifications
    WHERE user_id = @current_user_id
      AND group_key IS NULL
      AND created_at > NOW() - INTERVAL '7 days'
)
SELECT * FROM grouped
UNION ALL
SELECT * FROM ungrouped
ORDER BY latest_at DESC
LIMIT 50;
```

---

## Problem 74: Design a Content Moderation System

**Difficulty:** Hard | **Frequency:** High (Trust & Safety)

```sql
CREATE TABLE moderation_reports (
    report_id UUID PRIMARY KEY,
    reporter_id UUID NOT NULL,
    content_type ENUM('post', 'comment', 'message', 'profile', 'image') NOT NULL,
    content_id UUID NOT NULL,
    content_owner_id UUID NOT NULL,
    reason ENUM('spam', 'harassment', 'hate_speech', 'violence', 'nudity', 'misinformation', 'copyright', 'other') NOT NULL,
    description TEXT,
    status ENUM('pending', 'in_review', 'actioned', 'dismissed', 'escalated') DEFAULT 'pending',
    priority ENUM('low', 'medium', 'high', 'critical') DEFAULT 'medium',
    auto_detection_score DECIMAL(5,4),  -- ML model confidence
    assigned_to UUID,  -- Moderator
    resolved_at TIMESTAMP,
    resolution_notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_status_priority (status, priority DESC, created_at),
    INDEX idx_content (content_type, content_id),
    INDEX idx_owner (content_owner_id)
);

CREATE TABLE moderation_actions (
    action_id UUID PRIMARY KEY,
    report_id UUID REFERENCES moderation_reports(report_id),
    content_type VARCHAR(50) NOT NULL,
    content_id UUID NOT NULL,
    target_user_id UUID NOT NULL,
    action_type ENUM('remove_content', 'warn_user', 'restrict_user', 'suspend_user', 'ban_user', 'no_action') NOT NULL,
    duration_hours INT,  -- For temporary restrictions
    reason TEXT,
    actioned_by UUID NOT NULL,  -- Moderator or 'system'
    is_appealed BOOLEAN DEFAULT FALSE,
    appeal_result ENUM('upheld', 'overturned'),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    INDEX idx_target (target_user_id, created_at DESC)
);

-- User strike system
CREATE TABLE user_strikes (
    user_id UUID NOT NULL,
    strike_number INT NOT NULL,
    reason VARCHAR(255) NOT NULL,
    report_id UUID REFERENCES moderation_reports(report_id),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    PRIMARY KEY (user_id, strike_number)
);
```

---

## Problem 75: Design a News Feed with Ranking Algorithm

**Difficulty:** Expert | **Frequency:** Very High (Facebook/Instagram interviews)

```sql
-- Posts (content items)
CREATE TABLE posts (
    post_id BIGINT PRIMARY KEY,
    user_id UUID NOT NULL,
    content TEXT,
    media_urls JSONB,
    post_type ENUM('text', 'image', 'video', 'link', 'poll') NOT NULL,
    visibility ENUM('public', 'friends', 'private') DEFAULT 'public',
    like_count INT DEFAULT 0,
    comment_count INT DEFAULT 0,
    share_count INT DEFAULT 0,
    engagement_score DECIMAL(10,4) DEFAULT 0,  -- Pre-computed ranking score
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_user_time (user_id, created_at DESC),
    INDEX idx_score (engagement_score DESC, created_at DESC)
);

-- Feed ranking signals
CREATE TABLE feed_interactions (
    user_id UUID NOT NULL,
    post_id BIGINT NOT NULL,
    interaction_type ENUM('view', 'like', 'comment', 'share', 'click', 'dwell', 'hide', 'report') NOT NULL,
    dwell_time_ms INT,  -- How long user looked at the post
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_user_time (user_id, created_at DESC),
    INDEX idx_post (post_id)
);

-- Relationship strength (for EdgeRank-like algorithm)
CREATE TABLE relationship_scores (
    user_id UUID NOT NULL,
    other_user_id UUID NOT NULL,
    affinity_score DECIMAL(5,4) NOT NULL DEFAULT 0,  -- 0 to 1
    last_interaction_at TIMESTAMP,
    interaction_count INT DEFAULT 0,
    PRIMARY KEY (user_id, other_user_id)
);
```

**Feed Ranking Query (simplified EdgeRank):**
```sql
-- Score = Affinity × Weight × Time_Decay
WITH candidate_posts AS (
    SELECT p.post_id, p.user_id, p.content, p.created_at,
           p.like_count, p.comment_count, p.share_count,
           COALESCE(rs.affinity_score, 0.1) AS affinity,
           -- Content type weight
           CASE p.post_type
               WHEN 'video' THEN 1.5
               WHEN 'image' THEN 1.3
               WHEN 'link' THEN 1.0
               ELSE 0.8
           END AS type_weight,
           -- Time decay (half-life of 6 hours)
           EXP(-0.693 * EXTRACT(EPOCH FROM (NOW() - p.created_at)) / 21600) AS time_decay,
           -- Engagement rate
           (p.like_count + p.comment_count * 3 + p.share_count * 5) AS engagement
    FROM posts p
    JOIN follows f ON p.user_id = f.following_id
    LEFT JOIN relationship_scores rs ON rs.user_id = @current_user_id AND rs.other_user_id = p.user_id
    WHERE f.follower_id = @current_user_id
      AND p.created_at > NOW() - INTERVAL '3 days'
      AND p.post_id NOT IN (SELECT post_id FROM feed_interactions WHERE user_id = @current_user_id AND interaction_type = 'hide')
)
SELECT post_id, content, created_at,
       (affinity * type_weight * time_decay * LOG(engagement + 1)) AS ranking_score
FROM candidate_posts
ORDER BY ranking_score DESC
LIMIT 20;
```

---

## Problem 76: Design a Comment System with Threading

**Difficulty:** Medium | **Frequency:** Very High

```sql
CREATE TABLE comments (
    comment_id BIGINT PRIMARY KEY,
    post_id BIGINT NOT NULL REFERENCES posts(post_id),
    user_id UUID NOT NULL,
    parent_comment_id BIGINT REFERENCES comments(comment_id),  -- NULL = top-level
    root_comment_id BIGINT REFERENCES comments(comment_id),  -- Top-most ancestor
    content TEXT NOT NULL,
    depth INT NOT NULL DEFAULT 0,
    path VARCHAR(1000),  -- Materialized path: "1/5/12/45"
    like_count INT DEFAULT 0,
    reply_count INT DEFAULT 0,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_post_time (post_id, created_at),
    INDEX idx_post_top (post_id, parent_comment_id, like_count DESC),  -- Top-level by likes
    INDEX idx_parent (parent_comment_id, created_at),
    INDEX idx_path (post_id, path)
);
```

**Get Threaded Comments (Reddit-style, sorted by best):**
```sql
-- Top-level comments sorted by engagement
WITH top_level AS (
    SELECT comment_id, user_id, content, like_count, reply_count, created_at
    FROM comments
    WHERE post_id = @post_id AND parent_comment_id IS NULL AND is_deleted = FALSE
    ORDER BY like_count DESC, created_at DESC
    LIMIT 20
),
-- First 3 replies for each top-level comment
replies AS (
    SELECT c.*, ROW_NUMBER() OVER (PARTITION BY c.root_comment_id ORDER BY c.like_count DESC) AS rn
    FROM comments c
    WHERE c.root_comment_id IN (SELECT comment_id FROM top_level)
      AND c.parent_comment_id IS NOT NULL
      AND c.is_deleted = FALSE
)
SELECT * FROM top_level
UNION ALL
SELECT comment_id, user_id, content, like_count, reply_count, created_at FROM replies WHERE rn <= 3
ORDER BY path;
```

---

## Problem 77: Design a User Block/Mute System

**Difficulty:** Medium | **Frequency:** High

```sql
CREATE TABLE user_blocks (
    blocker_id UUID NOT NULL,
    blocked_id UUID NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (blocker_id, blocked_id),
    INDEX idx_blocked (blocked_id)
);

CREATE TABLE user_mutes (
    user_id UUID NOT NULL,
    muted_id UUID NOT NULL,
    mute_type ENUM('user', 'keyword', 'hashtag') DEFAULT 'user',
    muted_value VARCHAR(255),  -- For keyword/hashtag mutes
    expires_at TIMESTAMP,  -- NULL = permanent
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, muted_id, mute_type)
);
```

**Feed query respecting blocks:**
```sql
SELECT p.*
FROM posts p
JOIN follows f ON p.user_id = f.following_id
WHERE f.follower_id = @current_user_id
  -- Respect blocks (bidirectional)
  AND NOT EXISTS (
      SELECT 1 FROM user_blocks ub 
      WHERE (ub.blocker_id = @current_user_id AND ub.blocked_id = p.user_id)
         OR (ub.blocker_id = p.user_id AND ub.blocked_id = @current_user_id)
  )
  -- Respect mutes
  AND NOT EXISTS (
      SELECT 1 FROM user_mutes um
      WHERE um.user_id = @current_user_id AND um.muted_id = p.user_id
        AND (um.expires_at IS NULL OR um.expires_at > NOW())
  )
ORDER BY p.created_at DESC
LIMIT 20;
```

---

## Problem 78: Design a Stories Feature (Instagram/Snapchat Stories)

**Difficulty:** Hard | **Frequency:** High

```sql
CREATE TABLE stories (
    story_id BIGINT PRIMARY KEY,
    user_id UUID NOT NULL,
    media_url VARCHAR(500) NOT NULL,
    media_type ENUM('image', 'video') NOT NULL,
    duration_seconds INT DEFAULT 5,  -- Display duration
    overlay_data JSONB,  -- Stickers, text overlays, filters
    visibility ENUM('public', 'close_friends', 'custom') DEFAULT 'public',
    view_count INT DEFAULT 0,
    expires_at TIMESTAMP NOT NULL,  -- 24 hours after creation
    is_highlight BOOLEAN DEFAULT FALSE,  -- Saved to highlights
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_user_active (user_id, expires_at DESC),
    INDEX idx_active (expires_at, created_at DESC)
);

CREATE TABLE story_views (
    story_id BIGINT NOT NULL REFERENCES stories(story_id),
    viewer_id UUID NOT NULL,
    viewed_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (story_id, viewer_id),
    INDEX idx_viewer (viewer_id, viewed_at DESC)
);

CREATE TABLE story_highlights (
    highlight_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    cover_image_url VARCHAR(500),
    display_order INT DEFAULT 0,
    INDEX idx_user (user_id, display_order)
);

CREATE TABLE highlight_stories (
    highlight_id UUID NOT NULL REFERENCES story_highlights(highlight_id),
    story_id BIGINT NOT NULL,
    display_order INT DEFAULT 0,
    PRIMARY KEY (highlight_id, story_id)
);
```

**Get stories from people I follow (story tray):**
```sql
SELECT u.user_id, u.username, u.avatar_url,
       COUNT(s.story_id) AS story_count,
       MAX(s.created_at) AS latest_story_at,
       BOOL_OR(sv.viewer_id IS NULL) AS has_unseen  -- Any unseen stories?
FROM follows f
JOIN users u ON f.following_id = u.user_id
JOIN stories s ON u.user_id = s.user_id AND s.expires_at > NOW()
LEFT JOIN story_views sv ON s.story_id = sv.story_id AND sv.viewer_id = @current_user_id
WHERE f.follower_id = @current_user_id
GROUP BY u.user_id, u.username, u.avatar_url
ORDER BY has_unseen DESC, latest_story_at DESC;
```

---

## Problem 79: Design a Poll/Voting System

**Difficulty:** Medium | **Frequency:** High

```sql
CREATE TABLE polls (
    poll_id UUID PRIMARY KEY,
    creator_id UUID NOT NULL,
    question TEXT NOT NULL,
    poll_type ENUM('single_choice', 'multiple_choice', 'ranked') DEFAULT 'single_choice',
    max_selections INT DEFAULT 1,
    is_anonymous BOOLEAN DEFAULT FALSE,
    show_results_before_vote BOOLEAN DEFAULT FALSE,
    allows_add_options BOOLEAN DEFAULT FALSE,
    total_votes INT DEFAULT 0,
    closes_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE poll_options (
    option_id UUID PRIMARY KEY,
    poll_id UUID NOT NULL REFERENCES polls(poll_id),
    option_text VARCHAR(500) NOT NULL,
    vote_count INT DEFAULT 0,
    display_order INT DEFAULT 0,
    added_by UUID,
    INDEX idx_poll (poll_id, display_order)
);

CREATE TABLE poll_votes (
    poll_id UUID NOT NULL,
    user_id UUID NOT NULL,
    option_id UUID NOT NULL REFERENCES poll_options(option_id),
    rank_position INT,  -- For ranked choice
    voted_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (poll_id, user_id, option_id),
    INDEX idx_option (option_id)
);
```

**Vote atomically (prevent double-voting on single-choice):**
```sql
BEGIN TRANSACTION;

-- Check if already voted
SELECT COUNT(*) FROM poll_votes 
WHERE poll_id = @poll_id AND user_id = @user_id;
-- If count > 0 and single_choice, reject

-- Cast vote
INSERT INTO poll_votes (poll_id, user_id, option_id) 
VALUES (@poll_id, @user_id, @option_id);

-- Update counts
UPDATE poll_options SET vote_count = vote_count + 1 WHERE option_id = @option_id;
UPDATE polls SET total_votes = total_votes + 1 WHERE poll_id = @poll_id;

COMMIT;
```

---

## Problem 80: Design a User Activity/Audit Log

**Difficulty:** Medium | **Frequency:** Very High (Compliance, Security)

```sql
CREATE TABLE activity_logs (
    log_id BIGINT PRIMARY KEY,  -- Snowflake ID (time-ordered)
    user_id UUID NOT NULL,
    session_id UUID,
    action VARCHAR(100) NOT NULL,  -- 'login', 'post.create', 'settings.update'
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    details JSONB,  -- Changed fields, old/new values
    ip_address INET,
    user_agent VARCHAR(500),
    geo_location JSONB,  -- {"country": "US", "city": "NYC", "lat": ..., "lng": ...}
    request_id UUID,  -- Correlation ID
    duration_ms INT,
    status ENUM('success', 'failure', 'error') DEFAULT 'success',
    created_at TIMESTAMP DEFAULT NOW(),
    -- Partitioned by month for retention management
    INDEX idx_user_time (user_id, created_at DESC),
    INDEX idx_action (action, created_at DESC),
    INDEX idx_resource (resource_type, resource_id, created_at DESC)
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE activity_logs_2024_01 PARTITION OF activity_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

**Architect Discussion:**
- Partition by time for easy retention management (DROP old partitions)
- At scale: Write to Kafka → Flink → ClickHouse for analytics
- Hot path (recent 30 days): PostgreSQL
- Cold path (historical): S3 + Athena/Presto
- Never store in same DB as application data (write amplification)

---

## Problem 81: Design a Hashtag Trending System

**Difficulty:** Hard | **Frequency:** High

```sql
CREATE TABLE hashtag_counts (
    hashtag_id INT NOT NULL,
    window_start TIMESTAMP NOT NULL,  -- 5-minute windows
    window_end TIMESTAMP NOT NULL,
    count INT NOT NULL DEFAULT 0,
    PRIMARY KEY (hashtag_id, window_start)
);

-- Trending: velocity of growth, not just absolute count
-- "Trending" = significant increase compared to baseline
```

**Calculate Trending Score:**
```sql
WITH current_window AS (
    SELECT hashtag_id, SUM(count) AS current_count
    FROM hashtag_counts
    WHERE window_start >= NOW() - INTERVAL '1 hour'
    GROUP BY hashtag_id
),
baseline AS (
    SELECT hashtag_id, AVG(count) AS avg_count
    FROM hashtag_counts
    WHERE window_start BETWEEN NOW() - INTERVAL '7 days' AND NOW() - INTERVAL '1 hour'
    GROUP BY hashtag_id
    HAVING AVG(count) > 0
)
SELECT h.tag, cw.current_count,
       b.avg_count AS baseline_hourly,
       (cw.current_count - b.avg_count) / b.avg_count AS velocity,
       -- Z-score for statistical significance
       (cw.current_count - b.avg_count) / GREATEST(STDDEV(b.avg_count), 1) AS z_score
FROM current_window cw
JOIN baseline b ON cw.hashtag_id = b.hashtag_id
JOIN hashtags h ON cw.hashtag_id = h.hashtag_id
WHERE cw.current_count > b.avg_count * 2  -- At least 2x baseline
ORDER BY velocity DESC
LIMIT 10;
```

**Architect:** In practice, trending uses:
- Redis Sorted Sets with time-decayed scores
- Apache Storm/Flink for real-time counting
- Sliding window with exponential decay
- Country/city-level trending (partition by geo)

---

## Problem 82: Design a User Reputation/Karma System (StackOverflow-like)

**Difficulty:** Hard | **Frequency:** High

```sql
CREATE TABLE reputation_events (
    event_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id UUID NOT NULL,
    event_type VARCHAR(50) NOT NULL,  -- 'answer_accepted', 'upvote_received', 'downvote_given'
    points INT NOT NULL,
    source_type VARCHAR(50),  -- 'question', 'answer', 'comment'
    source_id UUID,
    granted_by UUID,  -- Who caused this (voter, acceptor)
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_user_time (user_id, created_at DESC)
);

-- Denormalized total (updated via trigger/event)
CREATE TABLE user_reputation (
    user_id UUID PRIMARY KEY,
    total_points INT NOT NULL DEFAULT 1,  -- Everyone starts at 1
    level VARCHAR(50) DEFAULT 'newcomer',
    -- Privilege thresholds
    can_upvote BOOLEAN GENERATED ALWAYS AS (total_points >= 15) STORED,
    can_downvote BOOLEAN GENERATED ALWAYS AS (total_points >= 125) STORED,
    can_comment BOOLEAN GENERATED ALWAYS AS (total_points >= 50) STORED,
    can_edit BOOLEAN GENERATED ALWAYS AS (total_points >= 2000) STORED,
    can_moderate BOOLEAN GENERATED ALWAYS AS (total_points >= 10000) STORED,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Reputation rules
CREATE TABLE reputation_rules (
    event_type VARCHAR(50) PRIMARY KEY,
    points INT NOT NULL,
    daily_cap INT,  -- Max points from this event type per day
    description VARCHAR(255)
);

INSERT INTO reputation_rules VALUES
('answer_upvoted', 10, 200, 'Your answer was upvoted'),
('question_upvoted', 5, 200, 'Your question was upvoted'),
('answer_accepted', 15, NULL, 'Your answer was accepted'),
('answer_downvoted', -2, NULL, 'Your answer was downvoted'),
('downvote_given', -1, NULL, 'You downvoted an answer'),
('bounty_awarded', 0, NULL, 'Variable: bounty amount'),
('spam_flag_confirmed', -100, NULL, 'Your post was confirmed as spam');
```

---

## Problem 83: Design a Media Upload & Processing Pipeline Schema

**Difficulty:** Hard | **Frequency:** High

```sql
CREATE TABLE media_uploads (
    media_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    original_filename VARCHAR(500),
    content_type VARCHAR(100) NOT NULL,  -- 'image/jpeg', 'video/mp4'
    file_size_bytes BIGINT NOT NULL,
    storage_bucket VARCHAR(100) NOT NULL,
    storage_key VARCHAR(500) NOT NULL,  -- S3 key
    
    -- Processing status
    status ENUM('uploading', 'processing', 'ready', 'failed', 'deleted') DEFAULT 'uploading',
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    error_message TEXT,
    
    -- Metadata (extracted after processing)
    width INT,
    height INT,
    duration_seconds DECIMAL(10,2),  -- For video/audio
    metadata JSONB,  -- EXIF data, codec info, etc.
    
    -- Content safety
    moderation_status ENUM('pending', 'safe', 'flagged', 'blocked') DEFAULT 'pending',
    moderation_labels JSONB,  -- ML-detected labels
    
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_user (user_id, created_at DESC),
    INDEX idx_status (status)
);

-- Processed variants (thumbnails, transcoded versions)
CREATE TABLE media_variants (
    variant_id UUID PRIMARY KEY,
    media_id UUID NOT NULL REFERENCES media_uploads(media_id),
    variant_type VARCHAR(50) NOT NULL,  -- 'thumbnail_sm', 'thumbnail_lg', '720p', '1080p'
    width INT,
    height INT,
    file_size_bytes BIGINT,
    storage_key VARCHAR(500) NOT NULL,
    cdn_url VARCHAR(500),
    INDEX idx_media (media_id, variant_type)
);
```

---

## Problem 84: Design a User Search (People Search)

**Difficulty:** Medium | **Frequency:** High

```sql
-- Search index table (denormalized for search)
CREATE TABLE user_search_index (
    user_id UUID PRIMARY KEY,
    username VARCHAR(30) NOT NULL,
    display_name VARCHAR(100),
    bio VARCHAR(500),
    follower_count INT DEFAULT 0,
    is_verified BOOLEAN DEFAULT FALSE,
    profile_completeness DECIMAL(3,2),  -- 0 to 1
    last_active_at TIMESTAMP,
    -- Full-text search
    search_vector TSVECTOR,  -- PostgreSQL
    INDEX idx_search (search_vector) USING GIN,
    INDEX idx_username_prefix (username varchar_pattern_ops)  -- For prefix search
);

-- Typeahead/autocomplete search
SELECT user_id, username, display_name, avatar_url, is_verified, follower_count
FROM user_search_index
WHERE username LIKE @query || '%'  -- Prefix match
   OR search_vector @@ plainto_tsquery(@query)  -- Full-text
ORDER BY 
    -- Exact username match first
    CASE WHEN username = @query THEN 0 ELSE 1 END,
    -- Verified users next
    CASE WHEN is_verified THEN 0 ELSE 1 END,
    -- Then by follower count (popularity)
    follower_count DESC
LIMIT 10;
```

---

## Problem 85: Design a Location Check-in System (Foursquare/Swarm)

**Difficulty:** Hard | **Frequency:** Medium

```sql
CREATE TABLE venues (
    venue_id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    address TEXT,
    latitude DECIMAL(10,8) NOT NULL,
    longitude DECIMAL(11,8) NOT NULL,
    total_checkins INT DEFAULT 0,
    total_unique_visitors INT DEFAULT 0,
    -- PostGIS geometry column for spatial queries
    location GEOMETRY(Point, 4326),
    INDEX idx_location USING GIST (location)
);

CREATE TABLE checkins (
    checkin_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    venue_id UUID NOT NULL REFERENCES venues(venue_id),
    message VARCHAR(500),
    latitude DECIMAL(10,8),
    longitude DECIMAL(11,8),
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_user_time (user_id, created_at DESC),
    INDEX idx_venue_time (venue_id, created_at DESC)
);

-- Find nearby venues (PostGIS)
SELECT venue_id, name, category,
       ST_Distance(location, ST_MakePoint(@lng, @lat)::geography) AS distance_meters
FROM venues
WHERE ST_DWithin(
    location,
    ST_MakePoint(@lng, @lat)::geography,
    1000  -- Within 1000 meters
)
ORDER BY distance_meters
LIMIT 20;
```

---

## Problem 86: Design a Content Sharing/Repost System

**Difficulty:** Medium | **Frequency:** High

```sql
CREATE TABLE shares (
    share_id BIGINT PRIMARY KEY,
    user_id UUID NOT NULL,
    original_post_id BIGINT NOT NULL REFERENCES posts(post_id),
    share_type ENUM('repost', 'quote', 'cross_platform') NOT NULL,
    comment TEXT,  -- For quote shares
    audience ENUM('public', 'friends', 'private') DEFAULT 'public',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE KEY uk_user_post_type (user_id, original_post_id, share_type),
    INDEX idx_original (original_post_id, created_at DESC),
    INDEX idx_user (user_id, created_at DESC)
);

-- "Who shared this" query with mutual connections prioritized
SELECT s.user_id, u.username, u.display_name, s.share_type, s.created_at,
       EXISTS(SELECT 1 FROM follows WHERE follower_id = @me AND following_id = s.user_id) AS is_following
FROM shares s
JOIN users u ON s.user_id = u.user_id
WHERE s.original_post_id = @post_id
ORDER BY is_following DESC, s.created_at DESC
LIMIT 50;
```

---

## Problem 87: Design a User Verification/Badge System

**Difficulty:** Medium | **Frequency:** Medium

```sql
CREATE TABLE verification_requests (
    request_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    type ENUM('identity', 'organization', 'government', 'notable') NOT NULL,
    status ENUM('pending', 'in_review', 'approved', 'rejected') DEFAULT 'pending',
    documents JSONB,  -- URLs to uploaded verification documents
    reviewer_id UUID,
    review_notes TEXT,
    submitted_at TIMESTAMP DEFAULT NOW(),
    reviewed_at TIMESTAMP,
    INDEX idx_status (status, submitted_at)
);

CREATE TABLE badges (
    badge_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    icon_url VARCHAR(500),
    badge_type ENUM('verified', 'achievement', 'subscription', 'custom') NOT NULL,
    criteria JSONB,  -- Auto-award criteria
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE user_badges (
    user_id UUID NOT NULL,
    badge_id INT NOT NULL REFERENCES badges(badge_id),
    awarded_at TIMESTAMP DEFAULT NOW(),
    awarded_by VARCHAR(50),  -- 'system', 'admin', 'subscription'
    expires_at TIMESTAMP,
    metadata JSONB,
    PRIMARY KEY (user_id, badge_id)
);
```

---

## Problem 88: Design a Real-time Collaboration Document (Google Docs-like)

**Difficulty:** Expert | **Frequency:** High

```sql
CREATE TABLE documents (
    doc_id UUID PRIMARY KEY,
    title VARCHAR(500) NOT NULL DEFAULT 'Untitled',
    owner_id UUID NOT NULL,
    current_version INT NOT NULL DEFAULT 1,
    content_snapshot TEXT,  -- Periodic full snapshots
    snapshot_version INT,
    visibility ENUM('private', 'shared', 'public') DEFAULT 'private',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Operational Transform / CRDT operations log
CREATE TABLE document_operations (
    operation_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    doc_id UUID NOT NULL REFERENCES documents(doc_id),
    user_id UUID NOT NULL,
    version INT NOT NULL,  -- Document version this op was based on
    operation_type ENUM('insert', 'delete', 'retain', 'format') NOT NULL,
    position INT NOT NULL,  -- Character position
    content TEXT,  -- For insert
    length INT,  -- For delete/retain
    attributes JSONB,  -- For formatting (bold, italic, etc.)
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_doc_version (doc_id, version),
    UNIQUE KEY uk_doc_version (doc_id, operation_id)
);

-- Document sharing/permissions
CREATE TABLE document_permissions (
    doc_id UUID NOT NULL REFERENCES documents(doc_id),
    user_id UUID,  -- NULL for link sharing
    permission ENUM('view', 'comment', 'edit', 'admin') NOT NULL,
    shared_via ENUM('direct', 'link', 'team') NOT NULL,
    link_token VARCHAR(100) UNIQUE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (doc_id, COALESCE(user_id, '00000000-0000-0000-0000-000000000000'))
);

-- Active editors (presence)
CREATE TABLE document_presence (
    doc_id UUID NOT NULL,
    user_id UUID NOT NULL,
    cursor_position INT,
    selection_start INT,
    selection_end INT,
    color VARCHAR(7),  -- User's cursor color
    last_heartbeat TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (doc_id, user_id)
);
```

**Architect Discussion:**
- Real-time sync: WebSocket + Redis Pub/Sub for broadcasting ops
- Conflict resolution: OT (Operational Transform) or CRDT (Conflict-free Replicated Data Types)
- Storage: Log of operations + periodic snapshots
- Rebuild document: Apply all ops since last snapshot
- At Google scale: Custom distributed log (Paxos-based)

---

## Problem 89: Design a Group/Community System (Facebook Groups / Discord Servers)

**Difficulty:** Hard | **Frequency:** High

```sql
CREATE TABLE communities (
    community_id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type ENUM('public', 'private', 'secret') NOT NULL DEFAULT 'public',
    category VARCHAR(100),
    member_count INT DEFAULT 0,
    post_count INT DEFAULT 0,
    rules JSONB,
    settings JSONB,
    created_by UUID NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_type_members (type, member_count DESC)
);

CREATE TABLE community_members (
    community_id UUID NOT NULL REFERENCES communities(community_id),
    user_id UUID NOT NULL,
    role ENUM('member', 'moderator', 'admin', 'owner') DEFAULT 'member',
    status ENUM('active', 'muted', 'banned') DEFAULT 'active',
    joined_at TIMESTAMP DEFAULT NOW(),
    invited_by UUID,
    PRIMARY KEY (community_id, user_id),
    INDEX idx_user (user_id)
);

-- Role-based permissions
CREATE TABLE community_role_permissions (
    community_id UUID NOT NULL,
    role VARCHAR(50) NOT NULL,
    permission VARCHAR(100) NOT NULL,  -- 'post.create', 'post.delete', 'member.kick'
    is_granted BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (community_id, role, permission)
);

-- Channels within a community (Discord-like)
CREATE TABLE channels (
    channel_id UUID PRIMARY KEY,
    community_id UUID NOT NULL REFERENCES communities(community_id),
    name VARCHAR(100) NOT NULL,
    type ENUM('text', 'voice', 'announcement', 'forum') DEFAULT 'text',
    topic VARCHAR(500),
    is_private BOOLEAN DEFAULT FALSE,
    display_order INT DEFAULT 0,
    category_name VARCHAR(100),  -- Channel category grouping
    INDEX idx_community (community_id, display_order)
);
```

---

## Problem 90: Design a User Relationship Graph (LinkedIn Connections)

**Difficulty:** Hard | **Frequency:** High

```sql
CREATE TABLE connections (
    user_id UUID NOT NULL,
    connected_user_id UUID NOT NULL,
    status ENUM('pending', 'accepted', 'declined', 'withdrawn') DEFAULT 'pending',
    connection_degree INT DEFAULT 1,  -- 1st, 2nd, 3rd degree
    connected_at TIMESTAMP,
    requested_at TIMESTAMP DEFAULT NOW(),
    requested_by UUID NOT NULL,  -- Who initiated
    message TEXT,  -- Connection request message
    PRIMARY KEY (user_id, connected_user_id),
    INDEX idx_status (user_id, status),
    CHECK (user_id < connected_user_id)  -- Canonical ordering to prevent duplicates
);

-- Endorsements
CREATE TABLE skill_endorsements (
    endorsed_user_id UUID NOT NULL,
    endorser_id UUID NOT NULL,
    skill VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (endorsed_user_id, endorser_id, skill),
    INDEX idx_skill (endorsed_user_id, skill)
);
```

**Find 2nd-degree connections (People You May Know):**
```sql
WITH my_connections AS (
    SELECT connected_user_id AS friend_id
    FROM connections
    WHERE user_id = @me AND status = 'accepted'
    UNION
    SELECT user_id AS friend_id
    FROM connections
    WHERE connected_user_id = @me AND status = 'accepted'
),
second_degree AS (
    SELECT c.connected_user_id AS suggestion,
           COUNT(*) AS mutual_count
    FROM connections c
    JOIN my_connections mc ON c.user_id = mc.friend_id
    WHERE c.status = 'accepted'
      AND c.connected_user_id != @me
      AND c.connected_user_id NOT IN (SELECT friend_id FROM my_connections)
    GROUP BY c.connected_user_id
)
SELECT sd.suggestion, u.display_name, sd.mutual_count
FROM second_degree sd
JOIN users u ON sd.suggestion = u.user_id
ORDER BY sd.mutual_count DESC
LIMIT 20;
```

---

## Architecture Patterns for Social Systems

| Challenge | Solution | Technology |
|-----------|----------|------------|
| Feed generation at scale | Fan-out on write + read hybrid | Redis Lists + SQL |
| Real-time messaging | Event-driven + WebSockets | Kafka + Redis Pub/Sub |
| Graph traversal (friends of friends) | Graph database or pre-computed | Neo4j / Cached adjacency |
| Trending detection | Sliding window counting | Redis Sorted Sets + Flink |
| Content ranking | ML scoring + feature store | Feature store + model serving |
| High write throughput (likes, views) | Buffer + batch write | Redis → Async batch to SQL |
| Global search | Inverted index | Elasticsearch |
| Media processing | Async pipeline | SQS → Lambda → S3 |
