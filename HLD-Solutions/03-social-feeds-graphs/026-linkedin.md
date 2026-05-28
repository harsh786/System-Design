# LinkedIn - System Design

## 1. Functional Requirements

### Core Features
- **Professional Profiles**: Education, work experience, skills, certifications, portfolio
- **Connection Graph**: 1st, 2nd, 3rd degree connections; follow without connecting
- **Feed**: Posts, articles, reposts, reactions (like/celebrate/support/insightful/funny)
- **Job Listings**: Post jobs, search jobs, apply, track applications, recruiter tools
- **Messaging**: 1:1 and group messaging, InMail (paid cold outreach)
- **Endorsements & Recommendations**: Skill endorsements, written recommendations
- **Company Pages**: Company profiles, employee lists, job postings, updates
- **Groups**: Professional interest groups with discussions
- **Notifications**: Connection requests, endorsements, job alerts, post interactions
- **Search**: People search, job search, company search, content search

### Out of Scope
- LinkedIn Learning (courses platform)
- Sales Navigator (advanced CRM)
- Recruiter Lite tooling
- LinkedIn Ads platform

---

## 2. Non-Functional Requirements

| Metric | Target |
|--------|--------|
| Availability | 99.99% (< 52 min downtime/year) |
| Feed Latency | < 200ms p99 |
| Search Latency | < 100ms p95 |
| Graph Query (degree check) | < 50ms p95 |
| Message Delivery | < 500ms |
| Total Registered Users | 900M |
| Monthly Active Users (MAU) | 300M |
| Daily Active Users (DAU) | 100M |
| Peak QPS (feed) | 500K |
| Data Durability | 99.999999999% (11 nines) |

### Consistency Model
- **Feed**: Eventual consistency (seconds acceptable)
- **Connections**: Strong consistency (graph mutations)
- **Messaging**: Causal consistency (ordered per conversation)
- **Job Applications**: Strong consistency (exactly-once submission)

---

## 3. Capacity Estimation

### Traffic
```
DAU: 100M
Avg sessions/day/user: 3
Avg feed loads/session: 5
Feed reads/day: 100M × 3 × 5 = 1.5B
Feed read QPS: 1.5B / 86400 ≈ 17K (avg), 500K (peak)

Posts created/day: 2M
Connection requests/day: 50M
Job applications/day: 10M
Messages sent/day: 300M
Search queries/day: 500M
```

### Storage
```
Profiles:
  900M users × 5KB avg = 4.5TB
  
Connection Graph:
  900M users × 500 avg connections = 450B edges (bidirectional = 225B unique)
  Each edge: 32 bytes (2 user_ids + metadata)
  225B × 32B = 7.2TB
  
Posts (last 5 years):
  2M/day × 365 × 5 = 3.65B posts
  Avg post size: 2KB text + metadata = ~7.3TB
  Media references: 30% have images/videos (stored in CDN)
  
Job Listings (active):
  20M active listings × 10KB = 200GB
  
Messages:
  300M/day × 365 × 3 years retention = 328B messages
  Avg 500 bytes = 164TB
  
Feed Cache (hot):
  100M DAU × 200 feed items × 200 bytes = 4TB (Redis)
```

### Bandwidth
```
Feed reads: 500K QPS × 50KB avg response = 25 GB/s outbound
Search: 200K QPS × 5KB = 1 GB/s
Total outbound: ~30 GB/s peak
```

---

## 4. Data Modeling

### PostgreSQL - Profiles & Jobs (Sharded by user_id / job_id)

```sql
-- User Profile (sharded by user_id)
CREATE TABLE users (
    user_id         BIGINT PRIMARY KEY,  -- Snowflake ID
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    headline        VARCHAR(300),
    summary         TEXT,
    location        VARCHAR(200),
    industry        VARCHAR(100),
    profile_photo   VARCHAR(500),  -- CDN URL
    banner_photo    VARCHAR(500),
    vanity_url      VARCHAR(100) UNIQUE,  -- linkedin.com/in/{vanity}
    visibility      ENUM('public', 'connections', 'private') DEFAULT 'public',
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- Work Experience
CREATE TABLE experiences (
    experience_id   BIGINT PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(user_id),
    company_id      BIGINT REFERENCES companies(company_id),
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    location        VARCHAR(200),
    start_date      DATE NOT NULL,
    end_date        DATE,  -- NULL = current
    is_current      BOOLEAN DEFAULT FALSE,
    INDEX idx_user (user_id),
    INDEX idx_company (company_id)
);

-- Education
CREATE TABLE education (
    education_id    BIGINT PRIMARY KEY,
    user_id         BIGINT NOT NULL,
    school_id       BIGINT REFERENCES schools(school_id),
    degree          VARCHAR(200),
    field_of_study  VARCHAR(200),
    start_year      INT,
    end_year        INT,
    grade           VARCHAR(50),
    activities      TEXT
);

-- Skills
CREATE TABLE user_skills (
    user_id         BIGINT NOT NULL,
    skill_id        BIGINT NOT NULL,
    endorsement_count INT DEFAULT 0,
    PRIMARY KEY (user_id, skill_id)
);

-- Endorsements
CREATE TABLE endorsements (
    endorsement_id  BIGINT PRIMARY KEY,
    user_id         BIGINT NOT NULL,       -- who is endorsed
    endorser_id     BIGINT NOT NULL,       -- who endorses
    skill_id        BIGINT NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, endorser_id, skill_id)
);

-- Recommendations
CREATE TABLE recommendations (
    recommendation_id BIGINT PRIMARY KEY,
    author_id       BIGINT NOT NULL,
    recipient_id    BIGINT NOT NULL,
    relationship    VARCHAR(200),  -- "managed directly"
    body            TEXT NOT NULL,
    status          ENUM('pending', 'accepted', 'hidden') DEFAULT 'pending',
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Job Listings
CREATE TABLE jobs (
    job_id          BIGINT PRIMARY KEY,
    company_id      BIGINT NOT NULL REFERENCES companies(company_id),
    poster_id       BIGINT NOT NULL REFERENCES users(user_id),
    title           VARCHAR(300) NOT NULL,
    description     TEXT NOT NULL,
    location        VARCHAR(200),
    is_remote       BOOLEAN DEFAULT FALSE,
    employment_type ENUM('full_time', 'part_time', 'contract', 'internship'),
    seniority_level ENUM('entry', 'associate', 'mid_senior', 'director', 'executive'),
    salary_min      INT,
    salary_max      INT,
    salary_currency VARCHAR(3) DEFAULT 'USD',
    skills_required JSONB,  -- [{skill_id, importance}]
    status          ENUM('active', 'closed', 'draft') DEFAULT 'active',
    applicant_count INT DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW(),
    expires_at      TIMESTAMP
);

-- Job Applications
CREATE TABLE applications (
    application_id  BIGINT PRIMARY KEY,
    job_id          BIGINT NOT NULL,
    user_id         BIGINT NOT NULL,
    resume_url      VARCHAR(500),
    cover_letter    TEXT,
    status          ENUM('submitted', 'viewed', 'shortlisted', 'rejected', 'hired'),
    applied_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (job_id, user_id)
);

-- Companies
CREATE TABLE companies (
    company_id      BIGINT PRIMARY KEY,
    name            VARCHAR(300) NOT NULL,
    vanity_url      VARCHAR(100) UNIQUE,
    logo_url        VARCHAR(500),
    industry        VARCHAR(100),
    company_size    VARCHAR(50),  -- "1001-5000"
    headquarters    VARCHAR(200),
    founded_year    INT,
    description     TEXT,
    website         VARCHAR(500),
    follower_count  INT DEFAULT 0
);

-- Posts / Content
CREATE TABLE posts (
    post_id         BIGINT PRIMARY KEY,
    author_id       BIGINT NOT NULL,
    content_type    ENUM('text', 'article', 'image', 'video', 'document', 'poll'),
    text_content    TEXT,
    media_urls      JSONB,  -- [{url, type, dimensions}]
    visibility      ENUM('public', 'connections', 'group') DEFAULT 'public',
    group_id        BIGINT,
    reaction_count  INT DEFAULT 0,
    comment_count   INT DEFAULT 0,
    repost_count    INT DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW(),
    INDEX idx_author_time (author_id, created_at DESC)
);

-- Reactions
CREATE TABLE reactions (
    user_id         BIGINT NOT NULL,
    post_id         BIGINT NOT NULL,
    reaction_type   ENUM('like', 'celebrate', 'support', 'funny', 'love', 'insightful'),
    created_at      TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, post_id)
);
```

### Graph Database (Custom / Neo4j-style) - Connections

```
Node: User {user_id, name, company, title, location}

Edge Types:
  CONNECTED_TO (bidirectional, weight=1)
    Properties: {connected_at, note}
  
  FOLLOWS (unidirectional)
    Properties: {followed_at}
  
  WORKED_AT (user -> company)
    Properties: {start, end, title}
  
  STUDIED_AT (user -> school)
    Properties: {start, end, degree}
  
  HAS_SKILL (user -> skill)
    Properties: {endorsement_count}
```

### Cassandra - Activity & Feed Storage

```cql
-- User feed (materialized/precomputed)
CREATE TABLE user_feed (
    user_id     BIGINT,
    feed_time   TIMEUUID,
    post_id     BIGINT,
    author_id   BIGINT,
    action_type TEXT,  -- 'posted', 'reacted', 'commented', 'connection_posted'
    relevance   FLOAT,
    PRIMARY KEY (user_id, feed_time)
) WITH CLUSTERING ORDER BY (feed_time DESC)
  AND default_time_to_live = 2592000;  -- 30 days TTL

-- Activity log (append-only)
CREATE TABLE activity_stream (
    actor_id    BIGINT,
    activity_time TIMEUUID,
    verb        TEXT,     -- 'post', 'react', 'connect', 'apply', 'endorse'
    object_type TEXT,     -- 'post', 'job', 'user', 'company'
    object_id   BIGINT,
    metadata    MAP<TEXT, TEXT>,
    PRIMARY KEY (actor_id, activity_time)
) WITH CLUSTERING ORDER BY (activity_time DESC);

-- Connection list (denormalized for fast lookup)
CREATE TABLE connections (
    user_id         BIGINT,
    connection_id   BIGINT,
    connected_at    TIMESTAMP,
    PRIMARY KEY (user_id, connection_id)
);
```

### Redis - Caches

```
# Feed cache (sorted set per user)
ZADD feed:{user_id} {score} {post_id}:{metadata_json}
ZREVRANGE feed:{user_id} 0 19  -- top 20 items

# Online presence
SET online:{user_id} 1 EX 300

# Connection count cache
HSET user_stats:{user_id} connections 523 followers 1204

# PYMK (People You May Know) precomputed
ZADD pymk:{user_id} {score} {suggested_user_id}

# 2nd degree connection cache (bloom filter)
BF.ADD 2nd_degree:{user_id} {other_user_id}

# Session & rate limiting
SET session:{token} {user_id} EX 86400
INCR ratelimit:{user_id}:{endpoint}:{minute}
```

### Elasticsearch - Search Indices

```json
// People Index
{
  "mappings": {
    "properties": {
      "user_id": {"type": "long"},
      "full_name": {"type": "text", "analyzer": "standard"},
      "headline": {"type": "text"},
      "location": {"type": "geo_point"},
      "location_text": {"type": "text"},
      "current_company": {"type": "keyword"},
      "current_title": {"type": "text"},
      "skills": {"type": "keyword"},  // array
      "industry": {"type": "keyword"},
      "connection_count": {"type": "integer"},
      "profile_strength": {"type": "float"},  // for ranking
      "past_companies": {"type": "keyword"},
      "schools": {"type": "keyword"}
    }
  }
}

// Jobs Index
{
  "mappings": {
    "properties": {
      "job_id": {"type": "long"},
      "title": {"type": "text", "analyzer": "job_title_analyzer"},
      "description": {"type": "text"},
      "company_name": {"type": "text"},
      "location": {"type": "geo_point"},
      "location_text": {"type": "text"},
      "is_remote": {"type": "boolean"},
      "skills_required": {"type": "keyword"},
      "seniority_level": {"type": "keyword"},
      "employment_type": {"type": "keyword"},
      "salary_min": {"type": "integer"},
      "salary_max": {"type": "integer"},
      "posted_at": {"type": "date"},
      "applicant_count": {"type": "integer"},
      "company_follower_count": {"type": "integer"}
    }
  }
}
```

---

## 5. High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                         │
│   [Web App]    [iOS App]    [Android App]    [3rd Party APIs]                    │
└───────────────────────────────────┬──────────────────────────────────────────────┘
                                    │ HTTPS/WSS
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           EDGE / GATEWAY LAYER                                    │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────────────┐          │
│  │   CDN    │  │  API Gateway │  │   WAF      │  │  Load Balancer   │          │
│  │(Akamai)  │  │  (Rate Limit │  │            │  │  (HAProxy/F5)    │          │
│  │          │  │   Auth, TLS) │  │            │  │                  │          │
│  └──────────┘  └──────────────┘  └────────────┘  └──────────────────┘          │
└───────────────────────────────────┬──────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         APPLICATION SERVICES LAYER                                │
│                                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ Feed Service │  │Graph Service │  │Search Service│  │  Job Service │        │
│  │              │  │              │  │              │  │              │        │
│  │- Aggregation │  │- Connections │  │- People      │  │- Listings    │        │
│  │- Ranking     │  │- Degree calc │  │- Jobs        │  │- Applications│        │
│  │- Fan-out     │  │- PYMK        │  │- Content     │  │- Matching    │        │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  Messaging   │  │Notification  │  │   Profile    │  │Recommendation│        │
│  │  Service     │  │  Service     │  │   Service    │  │   Engine     │        │
│  │              │  │              │  │              │  │              │        │
│  │- 1:1 / Group │  │- Push/Email  │  │- CRUD        │  │- Content     │        │
│  │- InMail      │  │- In-app      │  │- Visibility  │  │- People      │        │
│  │- Presence    │  │- Digests     │  │- Media       │  │- Jobs        │        │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                           │
│  │  Identity /  │  │   Content    │  │  Analytics   │                           │
│  │  Auth (SSO)  │  │   Service    │  │   Service    │                           │
│  │              │  │              │  │              │                           │
│  │- OAuth 2.0   │  │- Posts/Media │  │- Profile views│                          │
│  │- RBAC        │  │- Articles    │  │- Post metrics│                           │
│  │- API tokens  │  │- Moderation  │  │- Who viewed  │                           │
│  └──────────────┘  └──────────────┘  └──────────────┘                           │
└───────────────────────────────────┬──────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       STREAM PROCESSING LAYER                                     │
│  ┌────────────────────────────────────────────────────────────────────┐          │
│  │                    Apache Kafka (Event Bus)                         │          │
│  │  Topics: activity, connections, posts, jobs, messages, analytics   │          │
│  └────────────────────────────────────────────────────────────────────┘          │
│                                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ Feed Builder │  │   Graph      │  │  Search      │  │   Metrics    │        │
│  │  (Samza)     │  │  Updater     │  │  Indexer     │  │  Aggregator  │        │
│  │              │  │  (Samza)     │  │  (Samza)     │  │  (Samza)     │        │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘        │
└───────────────────────────────────┬──────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          DATA STORAGE LAYER                                       │
│                                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  Espresso    │  │  Voldemort   │  │   Cassandra  │  │    Redis     │        │
│  │ (MySQL-based │  │ (Key-Value   │  │  (Activity   │  │  (Feed Cache │        │
│  │  doc store)  │  │  read-heavy) │  │   Timelines) │  │   Sessions)  │        │
│  │              │  │              │  │              │  │              │        │
│  │- Profiles    │  │- Graph edges │  │- Feed store  │  │- Hot feeds   │        │
│  │- Jobs        │  │- Counters    │  │- Messages    │  │- PYMK cache  │        │
│  │- Companies   │  │- Configs     │  │- Activities  │  │- Rate limits │        │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                           │
│  │Elasticsearch │  │   HDFS /     │  │  Blob Store  │                           │
│  │              │  │  Spark       │  │  (Azure/S3)  │                           │
│  │- People idx  │  │              │  │              │                           │
│  │- Job idx     │  │- ML training │  │- Images      │                           │
│  │- Content idx │  │- Analytics   │  │- Videos      │                           │
│  │              │  │- Graph dumps │  │- Documents   │                           │
│  └──────────────┘  └──────────────┘  └──────────────┘                           │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Feed Generation Flow

```
┌──────┐     ┌──────────┐     ┌─────────────┐     ┌──────────┐
│ User │────▶│ Post     │────▶│   Kafka     │────▶│  Feed    │
│posts │     │ Service  │     │(post topic) │     │ Builder  │
└──────┘     └──────────┘     └─────────────┘     │ (Samza)  │
                                                   └────┬─────┘
                                                        │
                    ┌───────────────────────────────────┐│
                    │  For each follower/connection:     ││
                    │  1. Fetch from Graph Service       ││
                    │  2. Compute relevance score        ││
                    │  3. Write to user's feed           ││
                    └───────────────────────────────────┘│
                                                        ▼
                                              ┌──────────────┐
                                              │  Cassandra   │
                                              │  (feed store)│
                                              └──────┬───────┘
                                                     │
                    ┌────────────────────────────────┐│
                    │  On feed read:                  ││
                    │  1. Check Redis cache           ││
                    │  2. If miss → Cassandra         ││
                    │  3. Apply real-time ranking     ││
                    │  4. Return top-N items          ││
                    └────────────────────────────────┘│
                                                     ▼
                                              ┌──────────────┐
                                              │    Redis     │
                                              │ (feed cache) │
                                              └──────────────┘
```

### Hybrid Fan-out Strategy

```
Celebrity/Influencer (>10K connections):
  → Fan-out on READ (pull model)
  → Store post, fetch at read time
  → Merge with precomputed feed

Regular User (<10K connections):
  → Fan-out on WRITE (push model)  
  → Write to all connections' feeds
  → Faster reads, more write amplification
```

---

## 6. Low-Level Design - APIs

### Feed APIs

```
GET /v2/feed
  Headers: Authorization: Bearer {token}
  Query: ?cursor={feed_time_uuid}&count=20&filter={all|posts|articles}
  
  Response 200:
  {
    "items": [
      {
        "feed_item_id": "uuid",
        "type": "post",
        "action": "connection_posted",  // why this is in your feed
        "actor": {
          "user_id": 12345,
          "name": "Jane Smith",
          "headline": "VP Engineering at TechCo",
          "profile_photo": "https://cdn.li/photos/12345.jpg",
          "degree": 1
        },
        "post": {
          "post_id": 98765,
          "text": "Excited to announce...",
          "media": [{"type": "image", "url": "..."}],
          "reactions": {"total": 234, "types": {"like": 150, "celebrate": 84}},
          "comments": 45,
          "reposts": 12,
          "created_at": "2024-01-15T10:30:00Z"
        },
        "relevance_score": 0.92
      }
    ],
    "next_cursor": "feed_time_uuid_next",
    "has_more": true
  }

POST /v2/posts
  Body:
  {
    "content_type": "text",
    "text": "Thrilled to share...",
    "media_ids": ["media_upload_id_1"],
    "visibility": "public",
    "mentions": [{"user_id": 555, "offset": 10, "length": 12}]
  }
  
  Response 201:
  {
    "post_id": 99001,
    "created_at": "2024-01-15T14:00:00Z"
  }
```

### Connection APIs

```
POST /v2/connections/invite
  Body:
  {
    "invitee_id": 67890,
    "message": "Hi, I'd love to connect..."
  }
  
  Response 201:
  {"invitation_id": "inv_abc123", "status": "pending"}

GET /v2/connections/{user_id}/degree?target_id={other_user_id}
  Response 200:
  {
    "degree": 2,
    "paths": [
      {"via": [{"user_id": 111, "name": "Bob"}]},
      {"via": [{"user_id": 222, "name": "Alice"}]}
    ]
  }

GET /v2/network/pymk?count=10
  Response 200:
  {
    "suggestions": [
      {
        "user_id": 44444,
        "name": "Sarah Connor",
        "headline": "ML Engineer at DeepTech",
        "mutual_connections": 12,
        "reason": "12 mutual connections",
        "score": 0.87
      }
    ]
  }
```

### Search APIs

```
GET /v2/search/people?q=machine+learning+engineer&location=San+Francisco
    &industry=technology&degree=1,2&page=1&count=10
  
  Response 200:
  {
    "total": 5420,
    "results": [
      {
        "user_id": 11111,
        "name": "Alex Johnson",
        "headline": "Senior ML Engineer at Google",
        "location": "San Francisco Bay Area",
        "degree": 2,
        "mutual_connections": 5,
        "match_score": 0.95
      }
    ],
    "facets": {
      "companies": [{"name": "Google", "count": 120}],
      "locations": [{"name": "SF Bay Area", "count": 3200}]
    }
  }

GET /v2/search/jobs?q=backend+engineer&location=remote&salary_min=150000
    &experience_level=mid_senior&posted_within=7d
  
  Response 200:
  {
    "total": 890,
    "results": [
      {
        "job_id": 77777,
        "title": "Senior Backend Engineer",
        "company": {"name": "Stripe", "logo": "..."},
        "location": "Remote",
        "salary_range": "$150K - $200K",
        "posted_at": "2024-01-14",
        "applicant_count": 45,
        "match_score": 0.88,
        "skills_match": ["Go", "Distributed Systems", "PostgreSQL"]
      }
    ]
  }
```

### Job Application API

```
POST /v2/jobs/{job_id}/apply
  Body:
  {
    "resume_id": "resume_abc",    // pre-uploaded
    "cover_letter": "Dear hiring manager...",
    "answers": [                  // screening questions
      {"question_id": "q1", "answer": "5 years"},
      {"question_id": "q2", "answer": "Yes"}
    ],
    "phone": "+1-555-0100"
  }
  
  Response 201:
  {
    "application_id": "app_xyz789",
    "status": "submitted",
    "applied_at": "2024-01-15T15:00:00Z"
  }
```

### Messaging API

```
POST /v2/messaging/conversations
  Body:
  {
    "participants": [67890],
    "message": {
      "text": "Hi! I saw your post about...",
      "type": "text"
    }
  }

GET /v2/messaging/conversations?cursor={ts}&count=20
  -- returns conversation list with last message preview

GET /v2/messaging/conversations/{conv_id}/messages?before={msg_id}&count=50
  -- returns paginated messages

WebSocket: wss://realtime.linkedin.com/messaging
  -- real-time message delivery & typing indicators
```

---

## 7. Deep Dive: People You May Know (PYMK)

### Algorithm Overview

PYMK is LinkedIn's most critical growth feature. It uses a multi-signal scoring system combining graph structure, profile similarity, and behavioral signals.

### Candidate Generation (Recall Phase)

```
Sources of candidates (union of all):

1. Friends-of-Friends (FoF):
   - All 2nd-degree connections
   - For user with 500 connections, each with 500:
     500 × 500 = 250,000 potential candidates (deduplicated)

2. Same Company:
   - Current and past colleagues not yet connected

3. Same School:
   - Alumni from same institution + graduation year overlap

4. Similar Profile:
   - Embedding-based similarity (title, skills, industry)
   - Use approximate nearest neighbor (ANN) search

5. Imported Contacts:
   - Email/phone contacts not yet connected on LinkedIn
```

### Scoring Formula

```
PYMK_Score(user_A, candidate_B) = Σ(wi × fi)

Where features fi and weights wi:

f1: mutual_connection_count / max_mutual          w1 = 0.35
f2: same_current_company                          w2 = 0.15
f3: same_school × recency_factor                  w3 = 0.10
f4: profile_similarity(embedding_cosine)          w4 = 0.10
f5: industry_match                                w5 = 0.05
f6: geographic_proximity                          w6 = 0.05
f7: interaction_signals (profile_views, etc.)     w7 = 0.10
f8: triangles_count(A, B)                         w8 = 0.10

Triangle Count:
  triangles(A, B) = |N(A) ∩ N(B)|
  where N(x) = set of neighbors of x
  
  Higher triangle density → stronger community signal
  
Profile Similarity:
  sim(A, B) = cosine(embed(A), embed(B))
  embed(x) = BERT(title + skills + industry + summary)
  
Recency Factor:
  recency(school) = exp(-λ × years_since_graduation)
  λ = 0.1 (slow decay)
```

### ML Ranking Model (Precision Phase)

```python
# Gradient Boosted Decision Tree (XGBoost/LightGBM)
# Trained on historical accept/ignore data

Features:
  # Graph features
  - mutual_connection_count: int
  - jaccard_similarity: float  # |N(A)∩N(B)| / |N(A)∪N(B)|
  - adamic_adar_score: float   # Σ 1/log(|N(z)|) for z in N(A)∩N(B)
  - preferential_attachment: float  # |N(A)| × |N(B)|
  - triangle_count: int
  
  # Profile features
  - same_company: bool
  - same_school: bool
  - same_industry: bool
  - title_similarity: float
  - skill_overlap: float
  - seniority_distance: int
  - location_distance_km: float
  
  # Behavioral features
  - profile_view_a_to_b: int (last 30 days)
  - profile_view_b_to_a: int
  - common_group_count: int
  - common_content_engagement: float
  
  # User-level features
  - connection_accept_rate_a: float
  - connection_accept_rate_b: float
  - days_since_last_login_b: int

Label: 1 if connection accepted, 0 if ignored/declined
Objective: Binary classification (probability of acceptance)
```

### Adamic-Adar Index (Key Graph Algorithm)

```
AA(A, B) = Σ [1 / log(|N(z)|)] for all z ∈ N(A) ∩ N(B)

Intuition: Mutual connections who themselves have few connections
           are stronger signals than those with many connections.
           
Example:
  Mutual connection with 50 connections:  1/log(50) = 0.59
  Mutual connection with 500 connections: 1/log(500) = 0.37
  → A selective connector as mutual friend is more meaningful
```

### Architecture

```
┌─────────────────────────────────────────────────────┐
│                PYMK Pipeline                         │
│                                                      │
│  ┌──────────┐     ┌───────────┐     ┌──────────┐   │
│  │Candidate │────▶│  Feature  │────▶│    ML    │   │
│  │Generator │     │  Builder  │     │  Ranker  │   │
│  │          │     │           │     │          │   │
│  │- FoF     │     │- Graph    │     │- GBDT    │   │
│  │- Company │     │- Profile  │     │- Top-K   │   │
│  │- School  │     │- Behavior │     │- Diverse │   │
│  │- ANN     │     │           │     │          │   │
│  └──────────┘     └───────────┘     └────┬─────┘   │
│                                           │          │
│                                           ▼          │
│                                    ┌──────────┐     │
│                                    │  Redis   │     │
│                                    │  Cache   │     │
│                                    │(per user)│     │
│                                    └──────────┘     │
└─────────────────────────────────────────────────────┘

Refresh cadence:
  - Full recompute: daily (offline Spark job)
  - Incremental update: on new connection event (Samza)
  - Cache TTL: 6 hours
```

---

## 8. Deep Dive: Professional Graph & Degree Separation

### Graph Properties
```
|V| = 900M nodes (users)
|E| = 225B edges (connections, bidirectional stored once)
Avg degree: 500
Diameter: ~6 (small world property)
Clustering coefficient: ~0.15 (higher than random due to professional communities)
```

### Degree Calculation: Bidirectional BFS

```python
def get_degree(source: int, target: int, max_degree: int = 3) -> int:
    """
    Bidirectional BFS to find shortest path (degree of separation).
    Meets in the middle for O(b^(d/2)) instead of O(b^d).
    For avg branching factor b=500 and d=3:
      Unidirectional: 500^3 = 125M nodes explored
      Bidirectional:  2 × 500^1.5 ≈ 22K nodes explored
    """
    if source == target:
        return 0
    
    # Check 1st degree (direct connection) - O(1) with adjacency hash
    if is_connected(source, target):
        return 1
    
    # Bidirectional BFS
    forward_visited = {source: 0}
    backward_visited = {target: 0}
    forward_queue = deque([source])
    backward_queue = deque([target])
    
    forward_depth = 0
    backward_depth = 0
    
    while forward_queue or backward_queue:
        # Expand from the smaller frontier
        if forward_queue and (not backward_queue or 
                              len(forward_queue) <= len(backward_queue)):
            forward_depth += 1
            if forward_depth + backward_depth > max_degree:
                return -1  # Beyond max degree
            
            next_level = []
            for _ in range(len(forward_queue)):
                node = forward_queue.popleft()
                for neighbor in get_connections(node):
                    if neighbor in backward_visited:
                        return forward_depth + backward_visited[neighbor]
                    if neighbor not in forward_visited:
                        forward_visited[neighbor] = forward_depth
                        next_level.append(neighbor)
            forward_queue.extend(next_level)
        else:
            # Expand backward similarly
            backward_depth += 1
            if forward_depth + backward_depth > max_degree:
                return -1
            # ... symmetric logic
    
    return -1  # Not reachable within max_degree
```

### Graph Partitioning Strategy

```
LinkedIn uses graph partitioning to distribute the social graph:

Strategy: Balanced Label Propagation (BLP)
  - Partition by geographic/industry clusters
  - Minimize cross-partition edges (reduces network hops)
  - Rebalance quarterly as graph evolves

Partition Layout:
  Partition 1: US West Coast tech professionals
  Partition 2: US East Coast finance professionals  
  Partition 3: European professionals
  Partition 4: Asia-Pacific professionals
  ... (hundreds of partitions)

Cross-partition queries:
  - 1st degree: single partition lookup (co-located with user)
  - 2nd degree: may span 2-3 partitions → parallel fan-out
  - 3rd degree: expensive, always precomputed/cached
```

### Precomputed 2nd-Degree Cache

```
Problem: 
  2nd-degree check for arbitrary pair requires intersection
  of two adjacency lists (500 × 500 = up to 250K comparisons)

Solution: Bloom filter per user for 2nd-degree set

BloomFilter specs per user:
  Expected set size: 500 × 500 = 250,000 (deduplicated ~150K)
  False positive rate: 1%
  Size: ~180KB per user
  
  Total: 900M × 180KB = 162TB (too large for memory)
  
Optimization: Only cache for active users (100M DAU)
  100M × 180KB = 18TB → fits in distributed Redis cluster

Refresh: Incremental on connection events
  When A connects to B:
    For each friend F of B:
      Add F to A's 2nd-degree bloom filter
    For each friend F of A:
      Add F to B's 2nd-degree bloom filter
```

### Degree Display Optimization

```
On profile view / search result, we need degree for each result:

Approach: Tiered lookup
  1. Check Redis bloom filter for 2nd degree → O(1)
  2. If bloom says NO → degree is 3+ (show "3rd+")
  3. If bloom says MAYBE → verify with graph DB
  4. For 1st degree → check connection list (Redis set)

This avoids expensive BFS for 95% of degree queries.

Latency:
  1st degree check: 1ms (Redis SISMEMBER)
  2nd degree bloom: 1ms (Redis BF.EXISTS)
  Verification (false positive): 5ms (graph DB)
  Average: < 2ms
```

### Graph Path Finding (for "How you're connected")

```python
def find_connection_paths(source: int, target: int, 
                          max_paths: int = 3) -> List[List[int]]:
    """
    Find up to max_paths shortest paths between two users.
    Used for "You're connected through: Alice, Bob, Charlie"
    """
    degree = get_degree(source, target)
    if degree == 1:
        return [[source, target]]
    if degree == 2:
        # Intersection of adjacency lists
        source_friends = get_connections(source)  # ~500
        target_friends = get_connections(target)  # ~500
        mutual = source_friends & target_friends
        # Rank by: connection strength, profile completeness, relevance
        ranked = rank_intermediaries(mutual, source, target)
        return [[source, m, target] for m in ranked[:max_paths]]
    if degree == 3:
        # More complex: 2-hop from source intersect 1-hop from target
        # Typically done asynchronously, cached
        paths = bfs_all_paths(source, target, max_depth=3, max_paths=3)
        return paths
    return []
```

---

## 9. Component Optimization

### LinkedIn's Espresso (Document Store)

```
Espresso = LinkedIn's custom distributed document store (built on MySQL)

Architecture:
  Router → Storage Node (MySQL instance) → Replication

Features:
  - Document-oriented on top of MySQL (schema flexibility)
  - Online schema changes (no downtime)
  - Change capture for downstream (feeding Kafka)
  - Multi-datacenter replication
  - Per-collection partitioning

Used for:
  - User profiles (partitioned by user_id)
  - Company pages
  - Job listings
  - Group data

Partitioning:
  Hash(user_id) % num_partitions → partition
  Each partition: primary + 2 replicas (cross-DC)
```

### Voldemort (Read-Heavy Key-Value)

```
Voldemort = LinkedIn's distributed KV store (open source)

Properties:
  - Eventually consistent (vector clocks)
  - Read-optimized (SSD-backed, memory-mapped)
  - Batch-computed data served with low latency

Used for:
  - Precomputed PYMK results
  - Connection degree caches  
  - Feature stores for ML models
  - Read-only derived datasets (bulk loaded from Hadoop)

Topology:
  - Consistent hashing with virtual nodes
  - Replication factor: 3
  - Read repair on divergence
```

### Kafka Architecture at LinkedIn

```
Kafka (invented at LinkedIn):

Cluster specs:
  - 100+ brokers per data center
  - 100K+ partitions
  - 7+ trillion messages/day
  - Multi-DC replication via MirrorMaker

Key Topics:
  ┌────────────────────────────────────────────────┐
  │ Topic                │ Partitions │ Retention   │
  ├────────────────────────────────────────────────┤
  │ member-activity      │ 1024       │ 7 days      │
  │ connection-events    │ 512        │ 7 days      │
  │ post-events          │ 256        │ 7 days      │
  │ job-events           │ 256        │ 7 days      │
  │ messaging-events     │ 512        │ 3 days      │
  │ notification-events  │ 256        │ 3 days      │
  │ search-indexing      │ 128        │ 1 day       │
  │ ml-features          │ 64         │ 30 days     │
  │ audit-log            │ 128        │ 90 days     │
  └────────────────────────────────────────────────┘

Schema: Avro with Schema Registry
Serialization: Protocol Buffers for internal RPC
```

### Samza Stream Processing

```
Samza (invented at LinkedIn):

Use cases:
  1. Feed Builder:
     Input: post-events topic
     Logic: For each post, fan-out to author's connections
     Output: Write to Cassandra feed tables + invalidate Redis cache
     
  2. Graph Updater:
     Input: connection-events topic
     Logic: Update adjacency lists, bloom filters, PYMK scores
     Output: Write to graph store + Voldemort

  3. Search Indexer:
     Input: profile-updates, job-events topics
     Logic: Transform to ES documents, batch index
     Output: Elasticsearch bulk API

  4. Notification Dispatcher:
     Input: Various event topics
     Logic: Deduplicate, aggregate (e.g., "5 people endorsed you")
     Output: Push notification / email queue

Processing guarantees:
  - At-least-once delivery
  - Idempotent writes (dedup key = event_id)
  - Checkpoint to Kafka consumer offsets
```

### Feed Ranking Algorithm

```python
def rank_feed_items(user_id: int, items: List[FeedItem]) -> List[FeedItem]:
    """
    Multi-objective ranking balancing relevance, freshness, and diversity.
    """
    user_profile = get_user_features(user_id)
    
    for item in items:
        # Base relevance
        creator_affinity = get_affinity_score(user_id, item.author_id)
        content_relevance = predict_engagement(user_profile, item)
        
        # Time decay
        age_hours = (now() - item.created_at).total_seconds() / 3600
        time_decay = 1.0 / (1.0 + 0.1 * age_hours)  # half-life ~10 hours
        
        # Social proof
        social_boost = log(1 + item.reaction_count) * 0.1
        
        # Network signal (connections who engaged)
        connection_engagement = count_connection_engagements(user_id, item.post_id)
        network_boost = min(connection_engagement * 0.15, 0.5)
        
        # Final score
        item.score = (
            0.4 * content_relevance +
            0.25 * creator_affinity +
            0.2 * time_decay +
            0.1 * social_boost +
            0.05 * network_boost
        )
    
    # Sort by score
    items.sort(key=lambda x: x.score, reverse=True)
    
    # Diversity pass: avoid consecutive posts from same author/company
    items = diversify(items, max_consecutive_same_source=2)
    
    return items

def predict_engagement(user: UserFeatures, item: FeedItem) -> float:
    """
    ML model predicting P(click) + P(like) + P(comment) + P(share)
    Trained on billions of historical interactions.
    """
    features = extract_features(user, item)
    # Deep learning model (transformer-based)
    p_click = model.predict(features, objective='click')
    p_like = model.predict(features, objective='like')
    p_comment = model.predict(features, objective='comment')
    p_share = model.predict(features, objective='share')
    
    # Weighted combination (comments/shares valued more)
    return 0.2*p_click + 0.3*p_like + 0.3*p_comment + 0.2*p_share
```

### Job Matching Algorithm

```python
def match_jobs_to_user(user_id: int) -> List[JobMatch]:
    """
    Computes job-user match score for recommendations.
    """
    user = get_user_profile(user_id)
    user_skills = set(get_user_skills(user_id))
    user_embedding = get_profile_embedding(user_id)
    
    # Candidate retrieval (ES query)
    candidates = es_search_jobs(
        title_similar_to=user.current_title,
        skills_overlap=user_skills,
        location=user.location_preference,
        seniority=user.seniority_level,
        limit=200
    )
    
    for job in candidates:
        job_skills = set(job.skills_required)
        
        # Skill match
        skill_overlap = len(user_skills & job_skills) / max(len(job_skills), 1)
        
        # Title/role similarity (embedding cosine)
        title_sim = cosine(user_embedding, get_job_embedding(job.job_id))
        
        # Company affinity (past interactions, follows, connections at company)
        company_score = get_company_affinity(user_id, job.company_id)
        
        # Seniority fit
        seniority_match = 1.0 - abs(user.seniority - job.seniority) * 0.25
        
        # Location fit
        location_score = compute_location_fit(user, job)
        
        # Salary fit (if available)
        salary_fit = compute_salary_fit(user.salary_expectation, 
                                         job.salary_min, job.salary_max)
        
        job.match_score = (
            0.30 * skill_overlap +
            0.20 * title_sim +
            0.15 * company_score +
            0.15 * seniority_match +
            0.10 * location_score +
            0.10 * salary_fit
        )
    
    candidates.sort(key=lambda j: j.match_score, reverse=True)
    return candidates[:50]
```

---

## 10. Observability, Privacy & Considerations

### Observability Stack

```
Metrics: InGraphs (LinkedIn's custom) + Prometheus
  - Feed latency (p50, p95, p99) per service
  - Graph query latency by degree
  - Kafka consumer lag per topic
  - Cache hit rates (Redis)
  - Error rates by endpoint
  - PYMK acceptance rate (product metric)

Tracing: Distributed tracing (custom, similar to Zipkin)
  - Request ID propagated across all services
  - Trace fan-out operations (feed generation)
  - Identify slow graph queries

Logging: Structured JSON → Kafka → HDFS → queryable via Hive/Presto
  - Audit logs for data access
  - Security events (auth failures, unusual patterns)

Alerting:
  - P99 > 500ms on any endpoint → page
  - Kafka consumer lag > 1M messages → page
  - Error rate > 0.1% → alert
  - Graph partition unreachable → page
```

### Privacy Controls

```
Profile Visibility Levels:
  1. Public (visible to all, indexed by search engines)
  2. Members only (logged-in LinkedIn users)
  3. Connections only (1st degree)
  4. Private (only self)

Granular controls:
  - Who can see connections list
  - Who can see last name
  - Profile viewing mode (visible / semi-anonymous / private)
  - Activity broadcasts (job changes, endorsements) on/off
  - Messaging (open to all / connections only / InMail only)
  - Discovery (appear in search / PYMK)

Implementation:
  - Visibility is a column on every data entity
  - Feed service checks visibility before including in feeds
  - Search index respects visibility (filter at query time)
  - PYMK respects "don't show me as suggestion" preference
```

### GDPR Compliance

```
Right to Access (Article 15):
  - Download Your Data: async export → ZIP file
  - Includes: profile, posts, messages, connections, search history
  - Implementation: Spark job scans all stores, assembles export

Right to Erasure (Article 17):
  - Account deletion pipeline:
    1. Soft delete immediately (flag account)
    2. Remove from search index (immediate)
    3. Remove from PYMK (next refresh cycle)
    4. Anonymize messages ("LinkedIn Member")
    5. Hard delete from all stores (within 30 days)
    6. Remove from backups (within 90 days)
  - Cascade: posts deleted, reactions anonymized, graph edges removed

Data Minimization:
  - Activity logs: 90-day retention for most
  - Search history: 6-month rolling window
  - Profile views: shown to user for 90 days, aggregated after

Consent Management:
  - Cookie consent banner (EU)
  - Marketing email opt-in/out
  - Data processing consent for ML features
  - Third-party data sharing consent
```

### Security Considerations

```
Authentication:
  - OAuth 2.0 + OpenID Connect
  - MFA (SMS, TOTP, security keys)
  - Session management (Redis, 24h access token, 30d refresh)

Anti-Scraping:
  - Rate limiting per endpoint (tiered by account type)
  - CAPTCHA on suspicious patterns
  - Headless browser detection
  - Connection viewing throttled (commercial use requires API license)

Data Protection:
  - Encryption at rest (AES-256)
  - Encryption in transit (TLS 1.3)
  - PII tokenization in logs
  - Field-level encryption for sensitive data (SSN in job apps)
```

### Scalability Considerations

```
Hot Spots:
  - Celebrity profiles (millions of followers)
    → Separate serving path, aggressive caching
  - Viral posts (millions of impressions in minutes)
    → Counter sharding, async aggregation
  - Job posting by major company (100K applications)
    → Application queue with backpressure

Multi-Region:
  - US West, US East, Europe, Asia-Pacific
  - Graph partitions replicated to nearest DC
  - Feed generated in user's home DC
  - Messages: home DC with async replication
  - Search: per-region indices with global fallback

Capacity Planning:
  - 10% monthly growth in graph edges
  - 5% monthly growth in content volume
  - Auto-scaling for compute (feed generation, search)
  - Provisioned capacity for storage (graph, messages)
```

---

## Summary

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Profile Store | Espresso (MySQL-based) | User/company/job data |
| Graph Store | Custom graph DB + Voldemort | Connections, degree calculation |
| Feed Storage | Cassandra | Materialized feed timelines |
| Feed Cache | Redis | Hot feed serving |
| Search | Elasticsearch | People, jobs, content search |
| Event Bus | Kafka | All async communication |
| Stream Processing | Samza | Feed building, indexing, notifications |
| ML Features | Voldemort + HDFS | Feature store for ranking |
| Media | CDN + Blob Store | Images, videos, documents |
| Messaging | Cassandra + WebSocket | Real-time message delivery |
| Analytics | HDFS + Spark + Presto | Offline analytics, ML training |
