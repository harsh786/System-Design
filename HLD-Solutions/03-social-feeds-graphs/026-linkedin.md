# Design LinkedIn - Professional Networking Platform

## 1. Functional Requirements

- **Profile**: Professional profile with experience, education, skills, endorsements
- **Connections**: Symmetric connections (both accept), 1st/2nd/3rd degree
- **Feed**: Professional content feed (posts, articles, job changes, milestones)
- **Jobs**: Job posting, search, application, recommendations
- **Messaging (InMail)**: Professional messaging with connection/InMail tiers
- **Search**: People, jobs, companies, content search with filters
- **Notifications**: Connection requests, endorsements, job alerts, post interactions
- **Company pages**: Business profiles with followers, job listings
- **Groups**: Professional community discussions
- **Learning**: LinkedIn Learning course platform
- **Recruiter tools**: Advanced search, InMail, pipeline management
- **Ads**: Sponsored content, InMail ads, display ads
- **Skills & Endorsements**: Skill verification, peer endorsements
- **Recommendations**: Written references from colleagues

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Availability | 99.99% |
| Feed load | < 300ms p50 |
| Search latency | < 200ms p50 |
| Scale | 900M+ members, 350M MAU |
| Connection graph | 50B+ edges (connections, follows) |
| Job postings | 20M+ active at any time |
| Feed posts/day | 2M+ (original content) |
| Profile views/day | 1B+ |

## 3. Capacity Estimation

| Metric | Value |
|---|---|
| Total members | 900M |
| DAU | 150M |
| Connections (avg per user) | 500 |
| Total graph edges | 50B+ |
| Posts/day | 2M |
| Feed loads/day | 15B |
| Job searches/day | 100M |
| Messages/day | 200M |
| Profile views/day | 1B |
| Notifications/day | 5B |

## 4. Data Modeling

```sql
-- Members
CREATE TABLE members (
    id BIGINT PRIMARY KEY,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    headline VARCHAR(220),
    industry VARCHAR(100),
    location VARCHAR(100),
    profile_photo_url TEXT,
    summary TEXT,
    connection_count INT DEFAULT 0,
    follower_count INT DEFAULT 0,
    open_to_work BOOLEAN DEFAULT FALSE,
    premium_type VARCHAR(20),
    created_at TIMESTAMP
);

-- Connections (symmetric graph)
CREATE TABLE connections (
    member_id BIGINT,
    connected_to BIGINT,
    status VARCHAR(20), -- pending, accepted, ignored
    connected_at TIMESTAMP,
    PRIMARY KEY (member_id, connected_to)
);
-- Bidirectional: both (A,B) and (B,A) inserted on acceptance

-- Experience
CREATE TABLE experiences (
    id BIGINT PRIMARY KEY,
    member_id BIGINT,
    company_id BIGINT,
    title VARCHAR(200),
    description TEXT,
    start_date DATE,
    end_date DATE, -- NULL if current
    location VARCHAR(100),
    is_current BOOLEAN DEFAULT FALSE
);

-- Jobs
CREATE TABLE jobs (
    id BIGINT PRIMARY KEY,
    company_id BIGINT,
    poster_id BIGINT,
    title VARCHAR(200),
    description TEXT,
    location VARCHAR(200),
    work_type VARCHAR(20), -- onsite, remote, hybrid
    experience_level VARCHAR(20), -- entry, mid, senior, director, executive
    skills_required TEXT[],
    salary_range JSONB, -- {min, max, currency}
    applicant_count INT DEFAULT 0,
    is_promoted BOOLEAN DEFAULT FALSE,
    posted_at TIMESTAMP,
    expires_at TIMESTAMP
);
CREATE INDEX idx_jobs_location_type ON jobs(location, work_type, experience_level);
```

## 5. High-Level Design

```
┌────────────────────────────────────────────────────────────────────────┐
│                        LINKEDIN ARCHITECTURE                            │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │ GRAPH SERVICE (Core - "Who knows whom")                        │    │
│  │ - 1st degree: direct connections                               │    │
│  │ - 2nd degree: friends of friends (for "People You May Know")   │    │
│  │ - 3rd degree: 2 hops away                                      │    │
│  │ - Graph traversal for connection path ("How you're connected") │    │
│  │ - Technology: custom graph store + caching                      │    │
│  │ - Scale: 900M nodes, 50B edges                                 │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │ Feed Service│ │ Job Service  │ │ Search Service│ │ Messaging    │  │
│  │ - Posts     │ │ - Postings   │ │ - People     │ │ - InMail     │  │
│  │ - Articles  │ │ - Applications│ │ - Jobs       │ │ - Chat       │  │
│  │ - Ranking   │ │ - Recommend  │ │ - Companies  │ │ - Groups     │  │
│  │ - Engagement│ │ - Alerts     │ │ - Content    │ │              │  │
│  └─────────────┘ └──────────────┘ └──────────────┘ └──────────────┘  │
│                                                                          │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │Notification │ │ Ads Platform │ │ Analytics    │ │ Recruiter    │  │
│  │  Service    │ │              │ │              │ │   Tools      │  │
│  └─────────────┘ └──────────────┘ └──────────────┘ └──────────────┘  │
└────────────────────────────────────────────────────────────────────────┘

Key Design Decisions:
- Graph service is central (drives PYMK, search ranking, feed relevance)
- "People You May Know" (PYMK): 2nd-degree connections who share:
  - Same company, same school, same city, mutual connections
  - ML model: P(will_connect | features)
- Feed ranking: professional relevance > recency
  - Signals: connection strength, content quality, topicality, timeliness
- Job recommendations: skill match + seniority + location + company preferences
```

## 6. APIs

```
GET /api/v2/feed?cursor=xxx&count=20
Response: {"elements": [posts with engagement, author info], "paging": {...}}

GET /api/v2/people/{member_id}
Response: {"profile": {full profile data, connection_degree, mutual_connections}}

POST /api/v2/connections/invite
Request: {"invitee_id": 123, "message": "Let's connect!"}
Response: {"status": "PENDING"}

GET /api/v2/jobs/search?keywords=engineer&location=SF&remote=true&page=1
Response: {"jobs": [...], "total": 5000, "facets": {...}}

POST /api/v2/jobs/{job_id}/apply
Request: {"resume_id": "r_1", "cover_letter": "...", "answers": [...]}
Response: {"application_id": "app_123", "status": "submitted"}

GET /api/v2/people/connections?member_id=123&degree=2&mutual=true
Response: {"connections": [...], "degree_info": {...}}
```

## 7. Graph Service Deep Dive

```
"People You May Know" (PYMK) Algorithm:
1. Get user's 1st-degree connections (500 avg)
2. For each 1st-degree: get THEIR connections (expand to 2nd degree)
3. Count mutual connections for each 2nd-degree candidate
4. Score: mutual_count × weight + same_company × 5 + same_school × 3 + same_city × 2
5. Filter: already connected, already rejected, blocked
6. ML re-rank: model trained on historical accept/reject data
7. Top 50 suggestions cached per user (refreshed daily)

Scalability:
- Full 2nd-degree expansion: 500 × 500 = 250K candidates (too expensive real-time)
- Optimization: precompute top 2nd-degree candidates offline (Spark job)
- Store precomputed PYMK in Redis (refresh batch daily, incremental on new connections)
- Online: re-rank cached candidates with fresh signals
```

## 8. Optimization

```
Feed Ranking (LinkedIn-specific):
- Content quality: text length, media, links vs empty shares
- Author authority: profile strength, follower count, industry expertise
- Network proximity: 1st degree > 2nd degree > followed
- Engagement velocity: likes/comments in first hour (viral detection)
- Negative signals: "I don't want to see this", unfollow, hide
- LinkedIn-specific: job changes, work anniversaries, skill endorsements get boost

Caching:
- Profile data: CDN + Memcached (heavy read)
- PYMK: Redis (precomputed, refreshed daily)
- Feed: Redis sorted set per user (TTL 5 min)
- Connection graph: in-memory graph store with caching tiers
- Job search results: Elasticsearch with result caching
```

## 9. Observability & Considerations

```yaml
Metrics: feed_engagement_rate, pymk_acceptance_rate, job_application_conversion
         search_click_through_rate, message_response_rate, graph_query_latency
```

### Key Trade-offs
| Choice | Benefit | Cost |
|---|---|---|
| Custom graph store | Optimized for social graph queries | Build/maintain custom infra |
| Batch PYMK computation | Don't compute expensive graph queries real-time | Suggestions lag new connections by hours |
| ML-ranked feed (not chronological) | Higher engagement, professional relevance | Complexity, may miss timely posts |
| Symmetric connections | Professional trust/validation | Limits growth vs asymmetric follow |
