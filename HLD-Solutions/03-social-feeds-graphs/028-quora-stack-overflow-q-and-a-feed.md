# Design Q&A Platform (Quora / Stack Overflow)

## 1. Problem Statement

Design a large-scale question-and-answer platform where users can ask questions, provide answers, vote on content quality, earn reputation, follow topics, and discover relevant content. The system must detect duplicate questions, rank answers by quality, and maintain a trust-based reputation system.

---

## 2. Functional Requirements

1. **Question Management**: Ask, edit, close, reopen, delete questions; add tags/topics
2. **Answer Management**: Post answers, edit, mark as accepted, convert to wiki
3. **Voting System**: Upvote/downvote questions and answers; score calculation
4. **Reputation System**: Earn/lose reputation based on community actions
5. **Badges & Privileges**: Award badges for achievements; unlock privileges at rep thresholds
6. **Topic/Tag Following**: Follow topics, get personalized feed
7. **Search & Discovery**: Full-text search, similar question suggestions, trending
8. **Duplicate Detection**: Detect and link duplicate questions
9. **Feed**: Personalized Q&A feed based on interests and expertise
10. **Comments**: Lightweight comments on questions/answers for clarification
11. **Moderation**: Flag, review queue, community moderation tools
12. **Notifications**: Answers to your questions, mentions, badge awards, followed topics

---

## 3. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Availability | 99.99% |
| Read Latency | < 100ms (p95) |
| Write Latency | < 300ms (p95) |
| Search Latency | < 200ms (p95) |
| Scale | 300M MAU, 50M questions, 200M answers |
| Consistency | Strong for votes/reputation, Eventual for feeds |
| Duplicate Detection | > 85% recall, < 5% false positive |
| SEO | Server-side rendering, structured data |

---

## 4. Capacity Estimation

### 4.1 Traffic

```
MAU: 300M
DAU: 50M
Questions asked/day: 500K
Answers posted/day: 2M
Votes cast/day: 50M
Comments/day: 5M
Searches/day: 100M
Page views/day: 2B (many from SEO/anonymous)

Write QPS:
  Questions: 500K / 86400 ≈ 6
  Answers: 2M / 86400 ≈ 23
  Votes: 50M / 86400 ≈ 580
  Comments: 5M / 86400 ≈ 58
  Total write: ~670 QPS (peak 3x: ~2,000)

Read QPS:
  Page views: 2B / 86400 ≈ 23,000
  Search: 100M / 86400 ≈ 1,160
  Feed: 50M × 5 loads / 86400 ≈ 2,900
  Total read: ~27,000 QPS (peak 3x: ~81,000)
```

### 4.2 Storage

```
Questions:
  50M questions × 5KB avg (title + body + metadata) = 250 GB

Answers:
  200M answers × 3KB avg = 600 GB

Votes:
  5B total votes × 20 bytes = 100 GB

Comments:
  500M comments × 500 bytes = 250 GB

User profiles + reputation:
  300M users × 2KB = 600 GB

Tags/Topics:
  1M tags × 1KB + 10B question-tag mappings × 16B = 161 GB

Text search index:
  ~3x raw text = 2.5 TB

Embeddings (for duplicate detection):
  50M questions × 768 dim × 4 bytes = 153 GB

Total: ~5 TB primary + indexes + replicas ≈ 20 TB
```

### 4.3 Bandwidth

```
Avg page size: 200KB (rendered)
Ingress: (500K questions × 5KB + 2M answers × 3KB) / 86400 = 100 MB/s
Egress: 2B × 200KB / 86400 = 46 Gbps
CDN offloads static assets (80%) → Origin: ~9 Gbps
```

---

## 5. Data Modeling

### 5.1 Question Schema (PostgreSQL, partitioned)

```sql
CREATE TABLE questions (
    question_id     BIGINT PRIMARY KEY,         -- Snowflake ID
    user_id         BIGINT NOT NULL,
    title           VARCHAR(300) NOT NULL,
    body            TEXT NOT NULL,              -- Markdown
    body_html       TEXT,                       -- Rendered HTML (cached)
    status          ENUM('open','closed','deleted','protected','locked'),
    close_reason    ENUM('duplicate','off_topic','unclear','too_broad','opinion'),
    accepted_answer_id BIGINT,
    score           INT DEFAULT 0,             -- upvotes - downvotes
    view_count      INT DEFAULT 0,
    answer_count    INT DEFAULT 0,
    comment_count   INT DEFAULT 0,
    bounty_amount   INT DEFAULT 0,
    bounty_expires  TIMESTAMP,
    is_wiki         BOOLEAN DEFAULT FALSE,
    duplicate_of    BIGINT,                    -- Link to canonical question
    last_activity   TIMESTAMP,                 -- Bumped on edit/answer
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP,
    INDEX idx_user (user_id),
    INDEX idx_score (score DESC),
    INDEX idx_activity (last_activity DESC),
    INDEX idx_created (created_at DESC)
);

CREATE TABLE question_tags (
    question_id     BIGINT,
    tag_id          INT,
    PRIMARY KEY (question_id, tag_id),
    INDEX idx_tag (tag_id, question_id)
);

CREATE TABLE question_revisions (
    revision_id     BIGINT PRIMARY KEY,
    question_id     BIGINT,
    user_id         BIGINT,
    title           VARCHAR(300),
    body            TEXT,
    edit_summary    VARCHAR(300),
    revision_num    INT,
    created_at      TIMESTAMP,
    INDEX idx_question (question_id, revision_num)
);
```

### 5.2 Answer Schema

```sql
CREATE TABLE answers (
    answer_id       BIGINT PRIMARY KEY,
    question_id     BIGINT NOT NULL,
    user_id         BIGINT NOT NULL,
    body            TEXT NOT NULL,
    body_html       TEXT,
    score           INT DEFAULT 0,
    is_accepted     BOOLEAN DEFAULT FALSE,
    is_wiki         BOOLEAN DEFAULT FALSE,
    comment_count   INT DEFAULT 0,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP,
    INDEX idx_question_score (question_id, is_accepted DESC, score DESC),
    INDEX idx_user (user_id)
);

CREATE TABLE answer_revisions (
    revision_id     BIGINT PRIMARY KEY,
    answer_id       BIGINT,
    user_id         BIGINT,
    body            TEXT,
    edit_summary    VARCHAR(300),
    revision_num    INT,
    created_at      TIMESTAMP
);
```

### 5.3 Voting Schema

```sql
CREATE TABLE votes (
    vote_id         BIGINT PRIMARY KEY,
    user_id         BIGINT NOT NULL,
    post_id         BIGINT NOT NULL,            -- question_id or answer_id
    post_type       ENUM('question','answer'),
    vote_type       ENUM('up','down','bookmark','spam','offensive'),
    created_at      TIMESTAMP,
    UNIQUE KEY uk_user_post (user_id, post_id, vote_type),
    INDEX idx_post (post_id, vote_type)
);

-- Materialized vote counts (denormalized for performance)
CREATE TABLE post_scores (
    post_id         BIGINT PRIMARY KEY,
    post_type       ENUM('question','answer'),
    upvotes         INT DEFAULT 0,
    downvotes       INT DEFAULT 0,
    score           INT DEFAULT 0,              -- upvotes - downvotes
    bookmark_count  INT DEFAULT 0,
    updated_at      TIMESTAMP
);
```

### 5.4 Reputation & Badge Schema

```sql
CREATE TABLE users (
    user_id         BIGINT PRIMARY KEY,
    username        VARCHAR(50) UNIQUE,
    display_name    VARCHAR(100),
    email           VARCHAR(255) UNIQUE,
    reputation      INT DEFAULT 1,
    gold_badges     INT DEFAULT 0,
    silver_badges   INT DEFAULT 0,
    bronze_badges   INT DEFAULT 0,
    is_moderator    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP
);

CREATE TABLE reputation_history (
    id              BIGINT PRIMARY KEY,
    user_id         BIGINT NOT NULL,
    amount          INT NOT NULL,               -- +10, -2, etc.
    reason          ENUM('answer_upvoted','answer_downvoted','question_upvoted',
                         'answer_accepted','answer_accept_given','bounty_earned',
                         'bounty_spent','edit_approved','spam_flag_confirmed',
                         'association_bonus'),
    post_id         BIGINT,
    created_at      TIMESTAMP,
    INDEX idx_user_time (user_id, created_at DESC)
);

CREATE TABLE badges (
    badge_id        INT PRIMARY KEY,
    name            VARCHAR(100),
    description     TEXT,
    type            ENUM('gold','silver','bronze'),
    category        ENUM('question','answer','participation','moderation','tag'),
    criteria_sql    TEXT,                       -- Automated badge criteria
    is_single       BOOLEAN DEFAULT TRUE       -- Can only earn once?
);

CREATE TABLE user_badges (
    id              BIGINT PRIMARY KEY,
    user_id         BIGINT,
    badge_id        INT,
    post_id         BIGINT,                    -- Related post (if applicable)
    awarded_at      TIMESTAMP,
    INDEX idx_user (user_id, awarded_at DESC)
);

-- Privilege thresholds
CREATE TABLE privileges (
    privilege_id    INT PRIMARY KEY,
    name            VARCHAR(100),
    description     TEXT,
    reputation_required INT,
    INDEX idx_rep (reputation_required)
);
-- Examples: 15=upvote, 50=comment, 125=downvote, 2000=edit, 3000=close_vote
```

### 5.5 Topic/Tag Following

```sql
CREATE TABLE tags (
    tag_id          INT PRIMARY KEY,
    name            VARCHAR(50) UNIQUE,
    description     TEXT,
    wiki_body       TEXT,
    question_count  INT DEFAULT 0,
    follower_count  INT DEFAULT 0,
    parent_tag_id   INT,                       -- Tag hierarchy
    is_synonym_of   INT                        -- Tag synonyms
);

CREATE TABLE user_tag_follows (
    user_id         BIGINT,
    tag_id          INT,
    notify          BOOLEAN DEFAULT TRUE,
    followed_at     TIMESTAMP,
    PRIMARY KEY (user_id, tag_id),
    INDEX idx_tag (tag_id)
);

CREATE TABLE user_tag_expertise (
    user_id         BIGINT,
    tag_id          INT,
    score           INT DEFAULT 0,             -- Answer score in this tag
    answer_count    INT DEFAULT 0,
    PRIMARY KEY (user_id, tag_id),
    INDEX idx_tag_score (tag_id, score DESC)   -- For "top answerers"
);
```

---

## 6. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         CLIENTS                                    │
│        (Web SSR / SPA / Mobile / API consumers)                   │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                     ┌─────▼──────┐
                     │    CDN     │  Static assets, cached pages
                     └─────┬──────┘
                           │
               ┌───────────▼───────────┐
               │     API Gateway       │
               │  (Auth, Rate Limit)   │
               └───────────┬───────────┘
                           │
         ┌─────────────────┼────────────────────────┐
         │                 │                        │
   ┌─────▼─────┐   ┌──────▼──────┐   ┌────────────▼────────────┐
   │  Question  │   │   Answer    │   │    Feed / Discovery     │
   │  Service   │   │   Service   │   │       Service           │
   └─────┬──────┘   └──────┬──────┘   └────────────┬────────────┘
         │                  │                       │
   ┌─────▼─────┐   ┌──────▼──────┐   ┌────────────▼────────────┐
   │   Vote    │   │ Reputation  │   │   Duplicate Detection   │
   │  Service  │   │  Service    │   │       Service           │
   └─────┬──────┘   └──────┬──────┘   └────────────┬────────────┘
         │                  │                       │
   ┌─────▼──────────────────▼───────────────────────▼────────────┐
   │                      DATA LAYER                              │
   │  ┌──────────┐  ┌─────────┐  ┌────────────┐  ┌───────────┐ │
   │  │PostgreSQL│  │  Redis  │  │Elasticsearch│  │   Kafka   │ │
   │  │ (Primary)│  │ (Cache) │  │  (Search)  │  │  (Events) │ │
   │  └──────────┘  └─────────┘  └────────────┘  └───────────┘ │
   │  ┌──────────┐  ┌─────────┐  ┌────────────┐               │
   │  │ Milvus   │  │ClickHse│  │  Flink     │               │
   │  │(Vectors) │  │(Analytics│  │(Streaming) │               │
   │  └──────────┘  └─────────┘  └────────────┘               │
   └──────────────────────────────────────────────────────────────┘
```

---

## 7. Low-Level Design & APIs

### 7.1 Question Service

```
POST /v1/questions
  Body: {title, body (markdown), tags[], bounty_amount?}
  Response: {question_id, url, similar_questions[]}
  Side effects: 
    - Trigger duplicate detection
    - Index in Elasticsearch
    - Notify tag followers
    - Generate embedding

GET /v1/questions/{id}
  Response: {question, answers[], comments[], related_questions[]}
  Caching: CDN 60s for anonymous, none for authenticated

PUT /v1/questions/{id}
  Body: {title?, body?, tags?, edit_summary}
  Auth: Owner OR reputation >= 2000

POST /v1/questions/{id}/close
  Body: {reason, duplicate_of?}
  Auth: reputation >= 3000 OR moderator
  
GET /v1/questions?tag=&sort=newest|votes|activity|unanswered&page=
```

### 7.2 Answer Service

```
POST /v1/questions/{id}/answers
  Body: {body (markdown)}
  Response: {answer_id}
  Side effects:
    - Notify question asker
    - Update question.answer_count
    - Trigger quality scoring

PUT /v1/answers/{id}
  Body: {body, edit_summary}

POST /v1/answers/{id}/accept
  Auth: Question owner only
  Side effects:
    - +15 rep to answerer, +2 rep to accepter
    - Update question.accepted_answer_id
```

### 7.3 Vote Service

```
POST /v1/posts/{id}/vote
  Body: {type: "up"|"down"}
  Auth: reputation >= 15 (upvote), >= 125 (downvote)
  Response: {new_score, vote_recorded}
  
  Business Rules:
    - One vote per user per post per type
    - Can change vote within 5 min or if post edited
    - Downvoting costs -1 rep to voter (answers only)
    - Upvote on answer: +10 rep to author
    - Upvote on question: +5 rep to author
    - Downvote on answer: -2 rep to author

DELETE /v1/posts/{id}/vote
  -- Undo vote (within time window)
```

### 7.4 Feed Service

```
GET /v1/feed?type=personalized|following|hot|newest&cursor=
  Response: {items[]: {type, question, preview_answer, score}, next_cursor}

Feed Generation Strategy:
  - Personalized: Questions from followed tags + topics user has expertise in
  - Hot: Wilson score interval ranking with time decay
  - Following: Activity from followed users/tags
  - Scoring: f(votes, answers, views, recency, user_interest_match)
```

### 7.5 Search API

```
GET /v1/search?q=&tags[]=&sort=relevance|votes|newest&page=
  Response: {results[]: {type, question, score, highlights}, total, facets}

GET /v1/search/similar?title=&body=
  Response: {similar_questions[]: {question_id, title, similarity_score}}
  -- Used during question creation for live duplicate suggestion
```

---

## 8. Deep Dive: Answer Quality Ranking

### 8.1 Ranking Signals

```
┌─────────────────────────────────────────────────────────────────┐
│                   ANSWER RANKING MODEL                            │
│                                                                   │
│  Input Features:                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ CONTENT SIGNALS          │ AUTHOR SIGNALS                  │  │
│  │ - Body length            │ - Total reputation              │  │
│  │ - Code block presence    │ - Tag-specific reputation       │  │
│  │ - Link count             │ - Answer acceptance rate        │  │
│  │ - Formatting quality     │ - Account age                   │  │
│  │ - Readability score      │ - Moderation history            │  │
│  │ - Edit count             │ - Badge count in topic          │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │ ENGAGEMENT SIGNALS       │ TEMPORAL SIGNALS                │  │
│  │ - Upvote count           │ - Time since posted             │  │
│  │ - Downvote count         │ - Time to first answer          │  │
│  │ - Bookmark count         │ - Last edit recency             │  │
│  │ - Comment count          │ - Vote velocity (recent votes)  │  │
│  │ - View-to-vote ratio     │ - Staleness (outdated content)  │  │
│  │ - Is accepted            │                                 │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  Output: quality_score ∈ [0, 1]                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Ranking Algorithm

```python
class AnswerRanker:
    """Ranks answers for display on question page."""
    
    def rank_answers(self, question, answers, viewer_id=None):
        scored = []
        for answer in answers:
            score = self.compute_score(answer, question, viewer_id)
            scored.append((answer, score))
        
        # Accepted answer always first (unless community disagrees heavily)
        scored.sort(key=lambda x: (
            x[0].is_accepted and x[0].score >= -3,  # Accepted + not terrible
            x[1]
        ), reverse=True)
        
        return [a for a, s in scored]
    
    def compute_score(self, answer, question, viewer_id):
        # Base score from votes (Wilson score lower bound for confidence)
        vote_score = self.wilson_score(answer.upvotes, answer.downvotes)
        
        # Expertise signal: author's reputation in question's tags
        tag_rep = self.get_tag_reputation(answer.user_id, question.tags)
        expertise_score = math.log1p(tag_rep) / 10  # Normalize
        
        # Content quality (ML model)
        content_score = self.content_quality_model.predict({
            'body_length': len(answer.body),
            'has_code': bool(re.search(r'```', answer.body)),
            'link_count': answer.body.count('http'),
            'formatting_score': self.assess_formatting(answer.body),
            'readability': textstat.flesch_reading_ease(answer.body),
        })
        
        # Freshness boost for newer answers (prevents incumbency advantage)
        age_days = (now() - answer.created_at).days
        freshness = 1.0 / (1.0 + age_days / 365)
        
        # Staleness penalty (outdated tech, broken links)
        staleness = self.detect_staleness(answer, question)
        
        # Combine signals
        final_score = (
            0.40 * vote_score +
            0.20 * expertise_score +
            0.20 * content_score +
            0.10 * freshness -
            0.10 * staleness
        )
        
        return final_score
    
    def wilson_score(self, upvotes, downvotes):
        """Wilson score interval lower bound (95% confidence)."""
        n = upvotes + downvotes
        if n == 0:
            return 0
        z = 1.96  # 95% confidence
        p = upvotes / n
        denominator = 1 + z*z/n
        centre = p + z*z/(2*n)
        spread = z * math.sqrt((p*(1-p) + z*z/(4*n)) / n)
        return (centre - spread) / denominator
    
    def detect_staleness(self, answer, question):
        """Detect if answer references outdated technologies."""
        # Check if answer mentions deprecated versions
        # Check if links are broken (async background check)
        # Check if newer answers have significantly more votes
        staleness = 0.0
        
        if answer.broken_link_count > 0:
            staleness += 0.3
        
        age_years = (now() - answer.created_at).days / 365
        if age_years > 3 and answer.last_edit_age_days > 365:
            staleness += 0.2
        
        # Technology-specific staleness detection
        if self.references_deprecated_api(answer.body, question.tags):
            staleness += 0.5
        
        return min(staleness, 1.0)
```

### 8.3 Real-Time Score Updates

```
Vote Event Flow:
1. User casts vote → Vote Service
2. Vote Service: Validate + persist + emit event to Kafka
3. Kafka → Score Aggregator (Flink):
   - Update post_scores table (atomic increment)
   - Update Redis cache for hot questions
   - Trigger re-rank if score changes significantly
4. Kafka → Reputation Service:
   - Credit/debit author reputation
   - Check badge eligibility

Flink Scoring Job:
  - Window: 5-second tumbling
  - Aggregates vote events per post
  - Batch-updates post_scores table
  - Emits "score_changed" events for websocket push
```

---

## 9. Deep Dive: Duplicate Question Detection

### 9.1 Architecture

```
┌──────────────────────────────────────────────────────────────┐
│              DUPLICATE DETECTION PIPELINE                      │
│                                                                │
│  ┌────────────┐    ┌──────────────┐    ┌──────────────────┐ │
│  │ New Question│───►│ Embedding    │───►│  Candidate       │ │
│  │  (title +   │    │ Generation   │    │  Retrieval       │ │
│  │   body)     │    │ (SBERT)      │    │  (ANN search)    │ │
│  └────────────┘    └──────────────┘    └────────┬─────────┘ │
│                                                   │           │
│                    ┌──────────────┐    ┌──────────▼─────────┐│
│                    │  Human       │◄───│  Re-ranking        ││
│                    │  Review      │    │  (Cross-encoder)   ││
│                    │  Queue       │    │  + Rule-based      ││
│                    └──────────────┘    └────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

### 9.2 Semantic Similarity Model

```python
class DuplicateDetector:
    def __init__(self):
        # Bi-encoder for fast retrieval
        self.bi_encoder = SentenceTransformer('all-MiniLM-L6-v2')  
        # Cross-encoder for precise re-ranking
        self.cross_encoder = CrossEncoder('ms-marco-MiniLM-L-12-v2')
        # Vector index
        self.index = MilvusClient(collection="question_embeddings")
    
    def find_duplicates(self, title: str, body: str, tags: list) -> list:
        """Find potential duplicate questions."""
        
        # Step 1: Generate query embedding
        query_text = f"{title} {body[:500]}"
        query_embedding = self.bi_encoder.encode(query_text)
        
        # Step 2: ANN search for candidates (fast, high recall)
        candidates = self.index.search(
            vector=query_embedding,
            limit=100,
            filter=f"tag IN {tags}" if tags else None,
            metric="cosine"
        )
        
        # Step 3: Tag-based filtering (must share at least 1 tag)
        if tags:
            candidates = [c for c in candidates if set(c.tags) & set(tags)]
        
        # Step 4: Cross-encoder re-ranking (slow but precise)
        pairs = [(query_text, c.title + " " + c.body[:500]) for c in candidates[:30]]
        cross_scores = self.cross_encoder.predict(pairs)
        
        # Step 5: Combine scores
        results = []
        for i, candidate in enumerate(candidates[:30]):
            combined_score = (
                0.3 * candidate.ann_score +    # Bi-encoder similarity
                0.5 * cross_scores[i] +         # Cross-encoder similarity
                0.1 * self.tag_overlap(tags, candidate.tags) +
                0.1 * self.title_lexical_sim(title, candidate.title)
            )
            if combined_score > 0.75:
                results.append({
                    'question_id': candidate.question_id,
                    'title': candidate.title,
                    'score': combined_score,
                    'confidence': 'high' if combined_score > 0.9 else 'medium'
                })
        
        return sorted(results, key=lambda x: x['score'], reverse=True)[:5]
    
    def title_lexical_sim(self, t1: str, t2: str) -> float:
        """Jaccard similarity on word tokens."""
        words1 = set(t1.lower().split())
        words2 = set(t2.lower().split())
        if not words1 or not words2:
            return 0
        return len(words1 & words2) / len(words1 | words2)
    
    def tag_overlap(self, tags1, tags2) -> float:
        s1, s2 = set(tags1), set(tags2)
        if not s1 or not s2:
            return 0
        return len(s1 & s2) / len(s1 | s2)
```

### 9.3 Live Duplicate Suggestion (As-You-Type)

```
User Types Title → Debounced API call (300ms) →
  POST /v1/search/similar?title=<partial_title>

Backend:
  1. Tokenize partial title
  2. Elasticsearch "more_like_this" query on title field
  3. If results > threshold, return top 5 suggestions
  4. Client shows: "Similar questions that may already have your answer"

On Submit:
  1. Full embedding-based duplicate detection
  2. If high-confidence duplicate found:
     - Show warning: "This may be a duplicate of..."
     - User can still submit (human review) or acknowledge duplicate
  3. If submitted anyway → enters moderation review queue
```

### 9.4 Embedding Index Maintenance

```
Index: Milvus collection "question_embeddings"
  - 50M vectors, 768 dimensions
  - Index type: IVF_FLAT (nlist=4096, nprobe=64)
  - Partitioned by top-level tag category (20 partitions)
  - Memory: 50M × 768 × 4B = 153 GB (fits in memory cluster)

Updates:
  - New question → generate embedding → insert into Milvus
  - Question edited significantly → re-embed → update vector
  - Question deleted/closed → soft-delete from index
  - Nightly: rebuild index partitions for optimal performance
```

---

## 10. Deep Dive: Reputation & Trust System

### 10.1 Reputation Rules

```
┌────────────────────────────────────────────────────────┐
│              REPUTATION POINT SYSTEM                     │
├────────────────────────────────────────────────────────┤
│ Action                          │ Rep Change           │
├─────────────────────────────────┼──────────────────────┤
│ Answer upvoted                  │ +10                  │
│ Question upvoted                │ +5                   │
│ Answer accepted                 │ +15                  │
│ Accepting an answer             │ +2                   │
│ Answer downvoted                │ -2                   │
│ Question downvoted              │ -2                   │
│ Casting a downvote              │ -1                   │
│ Bounty offered                  │ -(bounty amount)     │
│ Bounty earned                   │ +(bounty amount)     │
│ Suggested edit approved         │ +2                   │
│ Post flagged as spam (confirmed)│ -100                 │
│ Association bonus               │ +100 (one-time)      │
├─────────────────────────────────┼──────────────────────┤
│ Daily reputation cap            │ +200 (excludes       │
│                                 │  bounties & accepts) │
└────────────────────────────────────────────────────────┘
```

### 10.2 Privilege Ladder

```python
PRIVILEGES = {
    1:     "create_posts",
    15:    "upvote",
    50:    "comment_everywhere",
    75:    "set_bounty",
    100:   "edit_wiki_posts",
    125:   "downvote",
    200:   "reduced_advertising",
    250:   "view_close_votes",
    500:   "retag_questions",
    1000:  "show_total_votes",
    1500:  "create_tags",
    2000:  "edit_others_posts",
    3000:  "cast_close_reopen_votes",
    4000:  "access_moderator_tools",
    5000:  "approve_tag_wiki_edits",
    10000: "protect_questions",
    15000: "trusted_user",         # Delete questions, no captcha
    20000: "access_analytics",
    25000: "site_wide_privileges",
}

class PrivilegeChecker:
    def can_perform(self, user, action) -> bool:
        required_rep = PRIVILEGES.get(action)
        if required_rep is None:
            return False
        if user.is_moderator:
            return True
        return user.reputation >= required_rep
```

### 10.3 Badge System

```python
BADGE_DEFINITIONS = {
    # Question Badges
    'Curious': ('bronze', 'Ask a well-received question on 5 separate days'),
    'Inquisitive': ('silver', 'Ask a well-received question on 30 separate days'),
    'Socratic': ('gold', 'Ask a well-received question on 100 separate days'),
    
    # Answer Badges
    'Teacher': ('bronze', 'Answer a question with score of 1 or more'),
    'Enlightened': ('silver', 'First to answer and accepted with 10+ score'),
    'Great Answer': ('gold', 'Answer score of 100 or more'),
    
    # Tag Badges
    'Tag Bronze': ('bronze', 'Earn 100+ score in tag with 20+ answers'),
    'Tag Silver': ('silver', 'Earn 400+ score in tag with 80+ answers'),
    'Tag Gold': ('gold', 'Earn 1000+ score in tag with 200+ answers'),
    
    # Participation
    'Yearling': ('silver', 'Active member for a year, 200+ reputation'),
    'Fanatic': ('gold', 'Visit the site each day for 100 consecutive days'),
}

class BadgeAwarder:
    """Background job that checks badge criteria periodically."""
    
    def check_badges_for_user(self, user_id):
        """Run daily per active user."""
        user = get_user(user_id)
        existing = get_user_badges(user_id)
        
        for badge_name, (tier, criteria) in BADGE_DEFINITIONS.items():
            if badge_name in existing and is_single_award(badge_name):
                continue
            if self.meets_criteria(user, badge_name):
                award_badge(user_id, badge_name)
                notify_user(user_id, f"You earned the {badge_name} badge!")
    
    def meets_criteria(self, user, badge_name) -> bool:
        """Evaluate badge-specific criteria."""
        # Each badge has a SQL query or programmatic check
        checker = self.badge_checkers[badge_name]
        return checker(user)
```

### 10.4 Anti-Gaming Measures

```
Vote Fraud Detection:
1. Serial voting detection (Flink streaming job):
   - If user A votes on > 3 posts by user B within 5 minutes → flag
   - Nightly reversal job: Undo serial votes, notify voter

2. Sock puppet detection:
   - Same IP + mutual voting pattern
   - Account creation proximity + voting correlation
   - ML model trained on confirmed sock puppet cases

3. Vote ring detection:
   - Graph analysis: Find cliques of users who exclusively vote for each other
   - PageRank anomaly: Users with high rep but low organic engagement

4. Rate limits:
   - Max 40 votes/day
   - Max 6 votes on same user's posts per day
   - Captcha after unusual voting patterns

Implementation:
  - Flink job consumes vote events
  - Maintains sliding window state per (voter, votee) pair
  - Emits fraud alerts to moderation queue
  - Nightly batch: Full graph analysis for vote rings
```

---

## 11. Component Architecture

### 11.1 Kafka Topics & Consumers

```
Topics:
  - question.created (500K/day) → partitions: 16
  - answer.created (2M/day) → partitions: 32
  - vote.cast (50M/day) → partitions: 128
  - comment.created (5M/day) → partitions: 32
  - user.reputation.changed → partitions: 64
  - post.edited → partitions: 16
  - moderation.flag → partitions: 8

Consumer Groups:
  - score-aggregator: vote.cast → Update post_scores
  - reputation-service: vote.cast → Update user reputation
  - badge-checker: vote.cast, question.created, answer.created → Check badges
  - notification-service: all → Send relevant notifications
  - search-indexer: question.*, answer.*, post.edited → Update ES
  - duplicate-detector: question.created → Generate embedding, check dupes
  - feed-updater: question.created, answer.created → Update user feeds
  - analytics: all → ClickHouse for dashboards
  - fraud-detector: vote.cast → Serial voting detection
```

### 11.2 Redis Cache Strategy

```
Cache Layers:
1. Question page cache (hot questions):
   Key: q:{question_id}:page → JSON (question + top answers)
   TTL: 60s (invalidated on vote/answer/edit)
   Hit rate: 85%

2. User reputation cache:
   Key: user:{user_id}:rep → INT
   TTL: 5 min (source of truth is DB)

3. Vote state cache (per viewer):
   Key: uv:{user_id}:{post_id} → "up"|"down"|null
   TTL: 1 hour
   Purpose: Show highlighted vote arrows

4. Tag question counts:
   Key: tag:{tag_id}:count → INT
   TTL: 10 min

5. Feed cache:
   Key: feed:{user_id}:{type} → LIST of question_ids
   TTL: 5 min

6. Rate limit counters:
   Key: rl:{user_id}:votes → ZSET (timestamps)
   TTL: 24 hours

Invalidation Strategy:
  - Event-driven: Kafka consumer invalidates relevant keys
  - Graceful: Serve stale + async refresh for non-critical data
```

### 11.3 Elasticsearch Configuration

```json
{
  "index": "questions",
  "settings": {
    "number_of_shards": 10,
    "number_of_replicas": 2,
    "analysis": {
      "analyzer": {
        "code_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "code_synonyms"]
        },
        "question_analyzer": {
          "type": "custom", 
          "tokenizer": "standard",
          "filter": ["lowercase", "stop", "snowball"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "title": {"type": "text", "analyzer": "question_analyzer", "boost": 3.0},
      "body": {"type": "text", "analyzer": "question_analyzer"},
      "code_blocks": {"type": "text", "analyzer": "code_analyzer"},
      "tags": {"type": "keyword"},
      "score": {"type": "integer"},
      "answer_count": {"type": "integer"},
      "has_accepted": {"type": "boolean"},
      "created_at": {"type": "date"},
      "last_activity": {"type": "date"},
      "view_count": {"type": "integer"}
    }
  }
}
```

### 11.4 Sharding Strategy

```
PostgreSQL (Citus or manual sharding):
  - questions: Shard by question_id (hash), 32 shards
  - answers: Shard by question_id (co-located with questions)
  - votes: Shard by post_id (co-located with questions/answers)
  - users: Shard by user_id, 16 shards
  - reputation_history: Shard by user_id (co-located with users)

Cross-shard queries:
  - "All answers by user X" → scatter-gather across answer shards
  - "User's reputation history" → single shard (user-sharded)
  - "Question + answers + votes" → single shard (co-located)
  
Read replicas:
  - 3 replicas per shard for read scaling
  - Async replication, ~100ms lag acceptable for reads
  - Strong reads (votes) go to primary
```

---

## 12. Feed Generation

### 12.1 Personalized Feed Algorithm

```python
class FeedGenerator:
    def generate_feed(self, user_id, feed_type, cursor, limit=25):
        if feed_type == 'personalized':
            return self.personalized_feed(user_id, cursor, limit)
        elif feed_type == 'hot':
            return self.hot_feed(cursor, limit)
        elif feed_type == 'following':
            return self.following_feed(user_id, cursor, limit)
    
    def personalized_feed(self, user_id, cursor, limit):
        # Get user's followed tags and expertise areas
        followed_tags = get_followed_tags(user_id)
        expertise_tags = get_expertise_tags(user_id, min_score=50)
        
        # Candidate sources
        candidates = []
        
        # 1. Questions in followed tags (50% of feed)
        candidates += self.get_tag_questions(
            followed_tags, limit=limit*3, min_score=-1
        )
        
        # 2. Unanswered questions in expertise areas (20%)
        candidates += self.get_unanswered_in_tags(
            expertise_tags, limit=limit*2
        )
        
        # 3. Hot questions site-wide (20%)
        candidates += self.get_hot_questions(limit=limit*2)
        
        # 4. Questions with bounties in relevant tags (10%)
        candidates += self.get_bounty_questions(
            followed_tags + expertise_tags, limit=limit
        )
        
        # Deduplicate and rank
        candidates = deduplicate(candidates)
        ranked = self.rank_feed_items(candidates, user_id)
        
        # Apply cursor and return
        return paginate(ranked, cursor, limit)
    
    def hot_score(self, question):
        """Reddit-style hot ranking with Q&A adjustments."""
        age_hours = (now() - question.created_at).total_seconds() / 3600
        
        # Base: logarithmic score
        score = math.log10(max(abs(question.score), 1))
        if question.score < 0:
            score = -score
        
        # Boost for answers and acceptance
        if question.answer_count > 0:
            score += 0.5
        if question.accepted_answer_id:
            score -= 0.3  # Less urgent, already answered
        
        # Time decay
        order = score - age_hours / 12
        
        return order
```

---

## 13. Observability

### 13.1 Key Metrics

```
Business Metrics:
  - Questions asked/day, answers/day
  - Answer rate (% questions with ≥1 answer)
  - Time to first answer (p50, p95)
  - Acceptance rate
  - Duplicate detection precision/recall
  - User retention (weekly active questioners/answerers)

System Metrics:
  - API latency by endpoint (p50/p95/p99)
  - Vote processing lag (event to score update)
  - Search relevance (click-through rate)
  - Cache hit rates per cache type
  - DB connection pool utilization
  - Kafka consumer lag per group

SLOs:
  - Question page load: 99.9% < 100ms
  - Vote acknowledgment: 99.9% < 200ms
  - Search results: 99.5% < 200ms
  - Duplicate detection: recall > 85%, precision > 95%
```

### 13.2 Distributed Tracing

```yaml
traces:
  question_page_load:
    spans:
      - api_gateway (auth, rate_limit): 5ms
      - question_service.get_question: 15ms
      - answer_service.get_answers: 20ms
      - redis_cache_check: 2ms
      - db_query (if cache miss): 30ms
      - render_markdown: 10ms
      - related_questions (ES): 25ms
    total_budget: 100ms

  vote_processing:
    spans:
      - api_gateway: 5ms
      - vote_service.validate: 10ms
      - vote_service.persist: 15ms
      - kafka_produce: 5ms
      - [async] score_update: 50ms
      - [async] reputation_update: 30ms
    sync_budget: 35ms
```

---

## 14. Key Considerations

### 14.1 SEO Optimization
- Server-side rendering for question pages
- Structured data (JSON-LD) for Q&A rich snippets
- Canonical URLs, proper meta tags
- Sitemap generation (50M question URLs)
- Static HTML caching at CDN for anonymous users

### 14.2 Content Quality
- Minimum body length requirements
- Quality filter: ML model flags low-quality posts for review
- First-post review queue for new users (rep < 50)
- Automatic comment conversion for non-answers
- Rate limiting: max 6 questions/day, 30 answers/day

### 14.3 Scalability Bottlenecks
- Hot questions: Dedicated Redis + read replicas for viral questions
- Vote storms: Batch vote counting (Flink window) vs real-time
- Search indexing lag: Acceptable 5s delay for new content searchability
- Reputation computation: Cached + async, eventual consistency acceptable

### 14.4 Data Integrity
- Vote uniqueness: Enforced at DB level (unique constraint)
- Reputation: Event-sourced, can recompute from history
- Edit history: Immutable append-only log
- Soft deletes everywhere (audit trail)

---

## 15. Summary

| Component | Technology | Scale |
|---|---|---|
| Primary DB | PostgreSQL (Citus) | 5 TB, 32 shards |
| Cache | Redis Cluster | 64 nodes, 2 TB |
| Search | Elasticsearch | 10 shards, 2.5 TB index |
| Vector Search | Milvus | 50M embeddings, 153 GB |
| Event Streaming | Kafka | 60M events/day |
| Stream Processing | Flink | Vote aggregation, fraud detection |
| Analytics | ClickHouse | Historical metrics |
| ML Serving | TorchServe | Duplicate detection, quality scoring |
| CDN | CloudFront | 95% cache hit for anonymous |

