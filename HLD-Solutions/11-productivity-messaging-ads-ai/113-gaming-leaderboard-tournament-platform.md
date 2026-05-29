# Gaming Leaderboard & Tournament Platform System Design

## 1. Functional Requirements

### Core Features
- **Real-Time Leaderboard**: Global, friends, regional rankings with instant updates
- **Score Submission**: Submit scores with anti-cheat validation
- **Tournament Brackets**: Single elimination, double elimination, round-robin, Swiss
- **Matchmaking**: ELO/Glicko-2 based skill matching
- **Seasonal Resets**: Periodic rank resets with rewards distribution
- **Rewards Distribution**: Currency, items, badges based on final standing
- **Spectator Mode**: Watch live matches in real-time

### Out of Scope
- Game engine / gameplay implementation
- Payment processing for in-game purchases
- Social features (chat, friends list) beyond leaderboard

## 2. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Leaderboard Update Latency | <500ms from score submit to board update |
| Rank Query (Top-K) | <50ms |
| Rank Query (User's rank) | <100ms for any user |
| Matchmaking Time | <30s for 95% of players |
| Availability | 99.95% (99.99% during tournaments) |
| Scale | 100M registered players, 10M concurrent |
| Tournament Size | Up to 1M participants per tournament |
| Score Throughput | 500K score submissions/sec (peak) |
| Consistency | Eventual for global board (1s), strong for tournaments |

## 3. Capacity Estimation

### Users & Activity
- 100M registered players, 10M concurrent peak
- Score submissions: 500K/sec peak (game ends, kills, achievements)
- Leaderboard queries: 2M QPS (auto-refresh every 10-30s)
- Active tournaments: 1000 concurrent
- Matchmaking requests: 100K/sec

### Storage
- Player profiles: 100M × 5KB = 500GB
- Score history: 500K/sec × 200B × 86400 = 8.6TB/day (retained 90 days = 770TB)
  - Aggregated: 100M players × 1KB × 90 days = 9TB
- Tournament data: 1000 active × 1M participants × 500B = 500GB
- Match history: 50M matches/day × 2KB = 100GB/day

### Compute
- Leaderboard sorted set operations: Redis cluster (100 nodes)
- Matchmaking: 50 instances (CPU-bound rating calculations)
- Tournament engine: 20 instances

### Bandwidth
- Leaderboard responses: 2M QPS × 2KB = 4GB/s
- Score ingestion: 500K/sec × 200B = 100MB/s
- WebSocket (spectator/live): 1M connections × 100B/sec = 100MB/s

## 4. Data Modeling

```sql
-- Players
CREATE TABLE players (
    player_id       UUID PRIMARY KEY,
    username        VARCHAR(50) UNIQUE NOT NULL,
    display_name    VARCHAR(100),
    avatar_url      VARCHAR(500),
    country         VARCHAR(2),
    region          VARCHAR(20), -- na, eu, asia, oceania
    -- Rating (Glicko-2)
    rating          FLOAT DEFAULT 1500.0,
    rating_deviation FLOAT DEFAULT 350.0,
    volatility      FLOAT DEFAULT 0.06,
    -- Stats
    games_played    INTEGER DEFAULT 0,
    wins            INTEGER DEFAULT 0,
    losses          INTEGER DEFAULT 0,
    draws           INTEGER DEFAULT 0,
    -- Season
    current_season_id UUID,
    season_rank     VARCHAR(20) DEFAULT 'bronze', -- bronze, silver, gold, platinum, diamond, master
    season_points   INTEGER DEFAULT 0,
    peak_rating     FLOAT DEFAULT 1500.0,
    -- Metadata
    last_active     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    is_banned       BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_players_rating ON players(rating DESC) WHERE NOT is_banned;
CREATE INDEX idx_players_region ON players(region, rating DESC);
CREATE INDEX idx_players_season ON players(current_season_id, season_points DESC);

-- Seasons
CREATE TABLE seasons (
    season_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    game_id         UUID NOT NULL,
    start_date      TIMESTAMPTZ NOT NULL,
    end_date        TIMESTAMPTZ NOT NULL,
    status          VARCHAR(20) DEFAULT 'upcoming', -- upcoming, active, ended
    reward_tiers    JSONB NOT NULL,
    /* {
        "diamond": {"min_points": 5000, "rewards": [{"type": "currency", "amount": 10000}]},
        "platinum": {"min_points": 3000, "rewards": [...]},
        ...
    } */
    reset_policy    JSONB NOT NULL -- {"soft_reset": true, "rating_decay": 0.75}
);

-- Score submissions
CREATE TABLE score_submissions (
    submission_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id       UUID NOT NULL,
    game_id         UUID NOT NULL,
    match_id        UUID,
    -- Score data
    score           BIGINT NOT NULL,
    score_type      VARCHAR(50) NOT NULL, -- kills, time, points, rank
    metadata        JSONB, -- game-specific: {kills: 15, deaths: 3, assists: 7}
    -- Validation
    replay_hash     VARCHAR(64), -- hash of game replay for verification
    anti_cheat_score FLOAT DEFAULT 1.0, -- 0=definitely cheating, 1=clean
    server_validated BOOLEAN DEFAULT FALSE,
    client_timestamp TIMESTAMPTZ,
    server_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Context
    game_mode       VARCHAR(50),
    map_id          VARCHAR(100),
    match_duration_sec INTEGER,
    CONSTRAINT fk_player FOREIGN KEY (player_id) REFERENCES players(player_id)
);

CREATE INDEX idx_scores_player_game ON score_submissions(player_id, game_id, server_timestamp DESC);
CREATE INDEX idx_scores_game_type ON score_submissions(game_id, score_type, score DESC);
CREATE INDEX idx_scores_match ON score_submissions(match_id);

-- Tournaments
CREATE TABLE tournaments (
    tournament_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    game_id         UUID NOT NULL,
    type            VARCHAR(30) NOT NULL, -- single_elimination, double_elimination, round_robin, swiss
    status          VARCHAR(20) DEFAULT 'registration', -- registration, in_progress, completed
    -- Configuration
    max_participants INTEGER NOT NULL,
    current_participants INTEGER DEFAULT 0,
    team_size       INTEGER DEFAULT 1, -- 1 for solo, 2-6 for teams
    rounds_total    INTEGER,
    current_round   INTEGER DEFAULT 0,
    -- Swiss-specific
    swiss_rounds    INTEGER, -- calculated as ceil(log2(participants))
    -- Scheduling
    registration_start TIMESTAMPTZ NOT NULL,
    registration_end   TIMESTAMPTZ NOT NULL,
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ,
    -- Seeding
    seeding_method  VARCHAR(20) DEFAULT 'rating', -- rating, random, manual
    -- Rewards
    prize_pool      JSONB, -- {"1st": [...], "2nd": [...], "top8": [...]}
    entry_fee       JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tournaments_status ON tournaments(status, start_time);
CREATE INDEX idx_tournaments_game ON tournaments(game_id, status);

-- Tournament brackets / matches
CREATE TABLE tournament_matches (
    match_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id   UUID NOT NULL,
    round_number    INTEGER NOT NULL,
    match_number    INTEGER NOT NULL, -- position in bracket
    bracket_type    VARCHAR(20) DEFAULT 'winners', -- winners, losers (double elim)
    -- Participants
    player1_id      UUID, -- NULL = BYE
    player2_id      UUID, -- NULL = BYE or TBD
    player1_seed    INTEGER,
    player2_seed    INTEGER,
    -- Result
    winner_id       UUID,
    loser_id        UUID,
    player1_score   INTEGER,
    player2_score   INTEGER,
    status          VARCHAR(20) DEFAULT 'pending', -- pending, in_progress, completed, forfeit
    -- Scheduling
    scheduled_time  TIMESTAMPTZ,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    -- Links
    next_match_id   UUID, -- winner goes here
    loser_match_id  UUID, -- loser goes here (double elim)
    CONSTRAINT fk_tournament FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id)
);

CREATE INDEX idx_tournament_matches_tournament ON tournament_matches(tournament_id, round_number, match_number);
CREATE INDEX idx_tournament_matches_player ON tournament_matches(tournament_id, player1_id);

-- Matchmaking queue
CREATE TABLE matchmaking_tickets (
    ticket_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id       UUID NOT NULL,
    game_mode       VARCHAR(50) NOT NULL,
    rating          FLOAT NOT NULL,
    rating_deviation FLOAT NOT NULL,
    region          VARCHAR(20) NOT NULL,
    -- Search parameters (expand over time)
    rating_range    INT4RANGE NOT NULL, -- initially tight, expands
    acceptable_ping_ms INTEGER DEFAULT 100,
    -- Party
    party_id        UUID, -- group queue
    party_size      INTEGER DEFAULT 1,
    -- Status
    status          VARCHAR(20) DEFAULT 'searching', -- searching, matched, cancelled, expired
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    matched_at      TIMESTAMPTZ,
    match_id        UUID
);

CREATE INDEX idx_matchmaking_active ON matchmaking_tickets(game_mode, region, rating) WHERE status = 'searching';
```

### Redis Schemas

```redis
# Global leaderboard (sorted set, score = negative for descending)
ZADD leaderboard:global:{game_id} {score} {player_id}
ZADD leaderboard:region:{game_id}:{region} {score} {player_id}
ZADD leaderboard:season:{season_id} {season_points} {player_id}

# Friends leaderboard (per user, small sorted set)
ZADD leaderboard:friends:{player_id}:{game_id} {score} {friend_id}

# Player rank cache
HSET player:rank:{player_id} global {rank} regional {rank} percentile {pct}

# Tournament live state
HSET tournament:state:{tournament_id} current_round 3 matches_pending 8

# Matchmaking pool (sorted set by rating for range queries)
ZADD matchmaking:pool:{game_mode}:{region} {rating} {ticket_id}

# Anti-cheat: rate limiting score submissions
SET anticheat:rate:{player_id} {count} EX 60

# Real-time match/spectator state
PUBLISH match:live:{match_id} {game_state_json}

# Player online status
SET player:online:{player_id} 1 EX 300
```

### Kafka Topics

```yaml
topics:
  scores.submitted:
    partitions: 128
    replication: 3
    retention: 7d
    key: player_id
  scores.validated:
    partitions: 64
    replication: 3
    retention: 30d
    key: game_id
  matchmaking.requests:
    partitions: 32
    replication: 3
    retention: 1h
    key: region
  tournament.events:
    partitions: 16
    replication: 3
    retention: 30d
    key: tournament_id
  leaderboard.updates:
    partitions: 64
    replication: 3
    retention: 24h
    key: game_id
```

## 5. High-Level Design (HLD)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────────────────┐  │
│  │  Game Client │  │  Web/Mobile  │  │  WebSocket (Live Updates)                │  │
│  │  (submits    │  │  Companion   │  │  - Leaderboard real-time                 │  │
│  │   scores)    │  │  App         │  │  - Match spectating                     │  │
│  └──────┬───────┘  └──────┬───────┘  │  - Tournament bracket updates           │  │
│         │                  │          └────────────────────┬─────────────────────┘  │
└─────────┼──────────────────┼──────────────────────────────┼─────────────────────────┘
          │                  │                               │
          ▼                  ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY + LOAD BALANCER                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │  Auth │ Rate Limit │ Anti-Cheat Header Validation │ WebSocket Upgrade │ WAF  │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────────┘
          │                  │                    │                    │
          ▼                  ▼                    ▼                    ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  Score           │ │  Leaderboard     │ │  Tournament      │ │  Matchmaking     │
│  Service         │ │  Service         │ │  Service         │ │  Service         │
│                  │ │                  │ │                  │ │                  │
│  - Submit score  │ │  - Top-K query   │ │  - Registration  │ │  - Queue ticket  │
│  - Validate      │ │  - User rank     │ │  - Bracket gen   │ │  - Find match    │
│  - Anti-cheat    │ │  - Friends board │ │  - Score report  │ │  - Rating calc   │
│  - Update board  │ │  - Regional      │ │  - Advancement   │ │  - Party match   │
└────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘
         │                    │                     │                     │
         ▼                    ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         MESSAGE BUS (Kafka)                                          │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │scores.submitted│  │scores.validated │  │tournament.events │  │leaderboard.* │  │
│  └────────────────┘  └─────────────────┘  └──────────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
         │                    │                     │                     │
         ▼                    ▼                     ▼                     ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  Anti-Cheat      │ │  Rating          │ │  Season          │ │  Notification    │
│  Worker          │ │  Calculator      │ │  Manager         │ │  Service         │
│                  │ │  (Glicko-2)      │ │                  │ │                  │
│  - Statistical   │ │  - Update after  │ │  - Track points  │ │  - Match found   │
│    analysis      │ │    each match    │ │  - Rank tiers    │ │  - Tournament    │
│  - Replay verify │ │  - Confidence    │ │  - Reset logic   │ │    updates       │
│  - Pattern detect│ │    intervals     │ │  - Rewards calc  │ │  - Rank changes  │
└────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘ └──────────────────┘
         │                    │                     │
         ▼                    ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                              │
│  ┌───────────────┐  ┌──────────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  PostgreSQL   │  │  Redis Cluster   │  │  ClickHouse  │  │  Object Storage   │  │
│  │               │  │  (100 nodes)     │  │              │  │                   │  │
│  │  - Players    │  │                  │  │  - Score     │  │  - Game replays   │  │
│  │  - Tournaments│  │  - Leaderboards  │  │    analytics │  │  - Replay files   │  │
│  │  - Matches    │  │  - Matchmaking   │  │  - Player    │  │                   │  │
│  │  - Seasons    │  │  - Live state    │  │    journey   │  │                   │  │
│  │               │  │  - Rate limits   │  │              │  │                   │  │
│  └───────────────┘  └──────────────────┘  └──────────────┘  └───────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD) - APIs

### Score Submission API

```http
POST /api/v1/scores/submit
Content-Type: application/json
Authorization: Bearer {game_server_token}
X-Anti-Cheat-Token: {encrypted_validation_token}

{
  "playerId": "player_abc123",
  "gameId": "game_fps_001",
  "matchId": "match_xyz789",
  "score": 2450,
  "scoreType": "points",
  "metadata": {
    "kills": 15,
    "deaths": 3,
    "assists": 7,
    "headshots": 8,
    "accuracy": 0.42,
    "matchDurationSec": 1200,
    "map": "dust2",
    "gameMode": "competitive"
  },
  "replayHash": "sha256_of_replay_file",
  "clientTimestamp": "2024-03-18T10:30:00Z"
}
```

**Response:**
```json
{
  "submissionId": "sub_def456",
  "status": "accepted",
  "newScore": 2450,
  "previousBest": 2100,
  "isNewPersonalBest": true,
  "rankChange": {
    "previousRank": 1523,
    "newRank": 1456,
    "change": +67
  },
  "seasonPointsAwarded": 25,
  "antiCheatStatus": "clean"
}
```

### Leaderboard Query API

```http
GET /api/v1/leaderboards/{game_id}?type=global&scope=all_time&page=1&pageSize=100
Authorization: Bearer {token}
```

**Response:**
```json
{
  "leaderboard": {
    "type": "global",
    "gameId": "game_fps_001",
    "totalPlayers": 5000000,
    "lastUpdated": "2024-03-18T10:30:05Z"
  },
  "entries": [
    {
      "rank": 1,
      "playerId": "player_001",
      "username": "ProGamer420",
      "displayName": "Pro Gamer",
      "avatar": "https://cdn.game.com/avatars/001.webp",
      "score": 99500,
      "country": "KR",
      "region": "asia",
      "rating": 2847,
      "seasonRank": "master",
      "stats": {"winRate": 0.78, "gamesPlayed": 1523}
    }
  ],
  "userPosition": {
    "rank": 45231,
    "score": 12400,
    "percentile": 95.5
  },
  "pagination": {"page": 1, "totalPages": 50000, "hasNext": true}
}
```

### Matchmaking API

```http
POST /api/v1/matchmaking/queue
Content-Type: application/json
Authorization: Bearer {token}

{
  "gameMode": "competitive_5v5",
  "region": "na",
  "partyId": "party_abc",
  "partyMembers": ["player_1", "player_2"],
  "preferences": {
    "maxPingMs": 80,
    "mapPreferences": ["dust2", "mirage"]
  }
}
```

**Response:**
```json
{
  "ticketId": "ticket_xyz",
  "status": "searching",
  "estimatedWait": "15s",
  "searchParameters": {
    "ratingRange": [1400, 1600],
    "region": "na",
    "expandsAfterSec": [15, 30, 60]
  },
  "wsChannel": "ws://match.game.com/queue/ticket_xyz"
}
```

## 7. Deep Dives

### Deep Dive 1: Real-Time Leaderboard at Scale

#### Problem: Rank query for 100M players in <100ms

```python
class ShardedLeaderboard:
    """
    Real-time leaderboard using Redis sorted sets with sharding.
    
    Architecture:
    - Top 10K: Single Redis sorted set (exact rank)
    - 10K-1M: Sharded sorted sets (approximate rank ±100)
    - 1M+: Percentile-based estimation
    
    Key insight: Most users only care about:
    1. Their exact rank (approximate is fine for mid-tail)
    2. Top players (exact from single set)
    3. Friends leaderboard (small set, exact)
    """
    
    TOP_K_SIZE = 10000
    SHARD_COUNT = 100  # Each shard holds ~1M players
    
    def __init__(self, redis_cluster):
        self.redis = redis_cluster
    
    async def update_score(self, game_id: str, player_id: str, new_score: int):
        """Update player's score and maintain leaderboard consistency."""
        # Update in appropriate shard
        shard = self._get_shard(player_id)
        await self.redis.zadd(
            f"leaderboard:shard:{game_id}:{shard}",
            {player_id: new_score}
        )
        
        # Check if qualifies for top-K
        top_k_min = await self.redis.zrangebyscore(
            f"leaderboard:top:{game_id}", 0, '+inf', start=0, num=1
        )
        
        if not top_k_min or new_score > int(top_k_min[0][1]):
            # Add to top-K, evict lowest if full
            await self.redis.zadd(f"leaderboard:top:{game_id}", {player_id: new_score})
            top_size = await self.redis.zcard(f"leaderboard:top:{game_id}")
            if top_size > self.TOP_K_SIZE:
                # Remove lowest
                await self.redis.zremrangebyrank(f"leaderboard:top:{game_id}", 0, 0)
        
        # Update shard count for rank estimation
        await self.redis.hincrby(f"leaderboard:counts:{game_id}", shard, 0)  # touch
    
    async def get_rank(self, game_id: str, player_id: str) -> dict:
        """
        Get player's rank efficiently.
        
        For top 10K: exact rank from top set (O(log N))
        For others: approximate using shard position + shard offset
        """
        # Check if in top-K
        rank_in_top = await self.redis.zrevrank(f"leaderboard:top:{game_id}", player_id)
        
        if rank_in_top is not None:
            return {"rank": rank_in_top + 1, "exact": True}
        
        # Approximate rank using sharded position
        shard = self._get_shard(player_id)
        
        # Rank within shard
        shard_rank = await self.redis.zrevrank(
            f"leaderboard:shard:{game_id}:{shard}", player_id
        )
        
        if shard_rank is None:
            return {"rank": None, "exact": False}
        
        # Get player's score
        score = await self.redis.zscore(
            f"leaderboard:shard:{game_id}:{shard}", player_id
        )
        
        # Count players with higher scores across all shards
        # (approximate: count in each shard above this score)
        total_above = self.TOP_K_SIZE  # Everyone in top-K is above
        pipe = self.redis.pipeline()
        for s in range(self.SHARD_COUNT):
            pipe.zcount(f"leaderboard:shard:{game_id}:{s}", f"({score}", "+inf")
        
        counts = await pipe.execute()
        total_above += sum(counts)
        
        return {"rank": total_above + 1, "exact": False, "estimate_error": "±50"}
    
    async def get_top_k(self, game_id: str, start: int, count: int) -> list:
        """Get top players. Uses dedicated top-K set for exact results."""
        if start + count <= self.TOP_K_SIZE:
            entries = await self.redis.zrevrange(
                f"leaderboard:top:{game_id}", start, start + count - 1,
                withscores=True
            )
            return [{"player_id": e[0], "score": int(e[1]), "rank": start + i + 1}
                    for i, e in enumerate(entries)]
        
        # Beyond top-K: merge from shards (more expensive)
        return await self._merge_shards_for_range(game_id, start, count)
    
    async def get_friends_leaderboard(self, player_id: str, game_id: str) -> list:
        """
        Friends leaderboard: small set, always exact.
        Maintained as separate sorted set per player.
        """
        entries = await self.redis.zrevrange(
            f"leaderboard:friends:{player_id}:{game_id}", 0, -1,
            withscores=True
        )
        return [{"player_id": e[0], "score": int(e[1]), "rank": i + 1}
                for i, e in enumerate(entries)]
    
    def _get_shard(self, player_id: str) -> int:
        """Consistent hashing for shard assignment."""
        return hash(player_id) % self.SHARD_COUNT


class LeaderboardSnapshotter:
    """
    Periodic materialization for historical snapshots.
    Runs hourly: captures full leaderboard state for analytics.
    """
    
    async def snapshot(self, game_id: str, season_id: str):
        """
        Capture current leaderboard to PostgreSQL/ClickHouse.
        Used for: season-end rewards, historical rank tracking, analytics.
        """
        timestamp = datetime.utcnow()
        
        # Export top 100K from Redis to DB (paginated)
        batch_size = 1000
        offset = 0
        
        while True:
            entries = await self.redis.zrevrange(
                f"leaderboard:top:{game_id}", offset, offset + batch_size - 1,
                withscores=True
            )
            if not entries:
                break
            
            rows = [
                (game_id, season_id, timestamp, offset + i + 1, 
                 entry[0], int(entry[1]))
                for i, entry in enumerate(entries)
            ]
            
            await self.db.batch_insert('leaderboard_snapshots', rows)
            offset += batch_size
```

#### Handling Ties

```python
class TieBreaker:
    """
    When multiple players have the same score, break ties with secondary criteria.
    
    Redis sorted set score encoding:
    score = primary_score * 10^10 + (MAX_TIMESTAMP - achievement_timestamp)
    
    This ensures: higher score first, then earlier achievement first (for same score)
    """
    
    MAX_TIMESTAMP = 9999999999  # Far future epoch
    
    def encode_score(self, primary_score: int, achieved_at: int) -> float:
        """Encode primary score + timestamp into single float for Redis."""
        # Higher primary score = higher rank
        # For same primary score: earlier timestamp = higher rank
        time_tiebreaker = self.MAX_TIMESTAMP - achieved_at
        return primary_score * 10_000_000_000 + time_tiebreaker
    
    def decode_score(self, encoded: float) -> tuple:
        """Decode back to (primary_score, achieved_at)."""
        primary = int(encoded // 10_000_000_000)
        time_tiebreaker = int(encoded % 10_000_000_000)
        achieved_at = self.MAX_TIMESTAMP - time_tiebreaker
        return primary, achieved_at
```

### Deep Dive 2: Matchmaking Algorithm

```python
from dataclasses import dataclass
from typing import List, Optional, Tuple
import time
import math

@dataclass
class MatchmakingTicket:
    ticket_id: str
    player_id: str
    rating: float
    rating_deviation: float
    region: str
    game_mode: str
    party_id: Optional[str]
    party_size: int
    max_ping_ms: int
    enqueued_at: float  # timestamp
    
    @property
    def wait_time(self) -> float:
        return time.time() - self.enqueued_at

class Glicko2Rating:
    """Glicko-2 rating system implementation."""
    
    TAU = 0.5  # System constant (constrains volatility change)
    
    def update_rating(self, player_rating: float, player_rd: float, 
                      player_vol: float, opponent_rating: float,
                      opponent_rd: float, outcome: float) -> Tuple[float, float, float]:
        """
        Update player's rating after a match.
        
        outcome: 1.0 = win, 0.5 = draw, 0.0 = loss
        Returns: (new_rating, new_rd, new_volatility)
        """
        # Convert to Glicko-2 scale
        mu = (player_rating - 1500) / 173.7178
        phi = player_rd / 173.7178
        mu_j = (opponent_rating - 1500) / 173.7178
        phi_j = opponent_rd / 173.7178
        
        # Step 3: g(phi) and E(mu, mu_j, phi_j)
        g_phi_j = 1 / math.sqrt(1 + 3 * phi_j**2 / math.pi**2)
        e_val = 1 / (1 + math.exp(-g_phi_j * (mu - mu_j)))
        
        # Step 4: Estimated variance
        v = 1 / (g_phi_j**2 * e_val * (1 - e_val))
        
        # Step 5: Delta
        delta = v * g_phi_j * (outcome - e_val)
        
        # Step 6: New volatility (iterative)
        new_vol = self._compute_volatility(phi, v, delta, player_vol)
        
        # Step 7: New RD
        phi_star = math.sqrt(phi**2 + new_vol**2)
        new_phi = 1 / math.sqrt(1/phi_star**2 + 1/v)
        
        # Step 8: New rating
        new_mu = mu + new_phi**2 * g_phi_j * (outcome - e_val)
        
        # Convert back
        new_rating = 173.7178 * new_mu + 1500
        new_rd = 173.7178 * new_phi
        
        return new_rating, new_rd, new_vol


class MatchmakingEngine:
    """
    Rating-based matchmaking with expanding search radius.
    
    Algorithm:
    1. Player enters queue with rating ± initial_range
    2. Every N seconds, expand acceptable range
    3. Match players whose ranges overlap
    4. Prioritize: closest rating → lowest wait time → region match
    5. Party matching: average party rating, ensure team balance
    """
    
    INITIAL_RATING_RANGE = 50
    EXPAND_INTERVAL_SEC = 5
    EXPAND_AMOUNT = 25
    MAX_RATING_RANGE = 500
    REMATCH_PREVENTION_WINDOW = 600  # Don't match same players within 10 min
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def process_queue(self, game_mode: str, region: str):
        """
        Main matchmaking loop. Runs continuously per region/mode.
        Finds optimal matches from the current queue.
        """
        # Get all active tickets for this region/mode
        tickets = await self._get_queue(game_mode, region)
        
        if len(tickets) < 2:
            return []
        
        # Sort by wait time (prioritize long-waiting players)
        tickets.sort(key=lambda t: t.enqueued_at)
        
        matches = []
        matched_ids = set()
        
        for ticket in tickets:
            if ticket.ticket_id in matched_ids:
                continue
            
            # Calculate current search range based on wait time
            range_expansion = int(ticket.wait_time / self.EXPAND_INTERVAL_SEC) * self.EXPAND_AMOUNT
            search_range = min(
                self.INITIAL_RATING_RANGE + range_expansion,
                self.MAX_RATING_RANGE
            )
            
            rating_min = ticket.rating - search_range
            rating_max = ticket.rating + search_range
            
            # Find best opponent
            best_match = await self._find_best_opponent(
                ticket, tickets, rating_min, rating_max, matched_ids
            )
            
            if best_match:
                matches.append((ticket, best_match))
                matched_ids.add(ticket.ticket_id)
                matched_ids.add(best_match.ticket_id)
        
        # Create matches and notify players
        for t1, t2 in matches:
            await self._create_match(t1, t2)
        
        return matches
    
    async def _find_best_opponent(self, ticket: MatchmakingTicket, 
                                   all_tickets: List[MatchmakingTicket],
                                   rating_min: float, rating_max: float,
                                   excluded: set) -> Optional[MatchmakingTicket]:
        """Find the best matching opponent for a ticket."""
        candidates = []
        
        for other in all_tickets:
            if other.ticket_id in excluded:
                continue
            if other.player_id == ticket.player_id:
                continue
            if other.party_id and other.party_id == ticket.party_id:
                continue
            
            # Rating range overlap check
            other_range = self.INITIAL_RATING_RANGE + int(other.wait_time / self.EXPAND_INTERVAL_SEC) * self.EXPAND_AMOUNT
            other_min = other.rating - min(other_range, self.MAX_RATING_RANGE)
            other_max = other.rating + min(other_range, self.MAX_RATING_RANGE)
            
            # Both must accept each other
            if (rating_min <= other.rating <= rating_max and 
                other_min <= ticket.rating <= other_max):
                
                # Check rematch prevention
                if await self._recently_matched(ticket.player_id, other.player_id):
                    continue
                
                # Score this candidate
                score = self._match_quality_score(ticket, other)
                candidates.append((score, other))
        
        if not candidates:
            return None
        
        # Return best quality match
        candidates.sort(key=lambda x: -x[0])
        return candidates[0][1]
    
    def _match_quality_score(self, t1: MatchmakingTicket, t2: MatchmakingTicket) -> float:
        """
        Score match quality (higher = better match).
        
        Factors:
        - Rating closeness (most important)
        - Wait time fairness (both waited similar time)
        - Rating deviation similarity
        """
        # Rating difference penalty (gaussian)
        rating_diff = abs(t1.rating - t2.rating)
        rating_score = math.exp(-(rating_diff**2) / (2 * 100**2))  # σ=100
        
        # Wait time consideration (longer wait = more lenient)
        avg_wait = (t1.wait_time + t2.wait_time) / 2
        wait_bonus = min(avg_wait / 60, 0.3)  # Up to 0.3 bonus for long waits
        
        return rating_score + wait_bonus
```

### Deep Dive 3: Tournament Engine

```python
import math
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class TournamentParticipant:
    player_id: str
    seed: int
    rating: float

class BracketGenerator:
    """
    Generates tournament brackets with proper seeding.
    Supports: single elimination, double elimination, Swiss.
    """
    
    def generate_single_elimination(self, participants: List[TournamentParticipant]) -> List[dict]:
        """
        Generate single elimination bracket.
        - Pad to next power of 2 with BYEs
        - Seed so that top seeds meet in later rounds
        - Standard seeding: 1v16, 2v15, 3v14... (but distributed across bracket)
        """
        n = len(participants)
        bracket_size = 2 ** math.ceil(math.log2(n))  # Next power of 2
        num_byes = bracket_size - n
        
        # Sort by seed (rating-based)
        participants.sort(key=lambda p: p.seed)
        
        # Generate seeded positions using standard tournament seeding
        positions = self._standard_seeding(bracket_size)
        
        matches = []
        round_num = 1
        match_num = 0
        
        for i in range(0, bracket_size, 2):
            pos1 = positions[i]
            pos2 = positions[i + 1]
            
            player1 = participants[pos1] if pos1 < n else None  # BYE
            player2 = participants[pos2] if pos2 < n else None  # BYE
            
            match = {
                'round': round_num,
                'match_number': match_num,
                'player1_id': player1.player_id if player1 else None,
                'player2_id': player2.player_id if player2 else None,
                'player1_seed': player1.seed if player1 else None,
                'player2_seed': player2.seed if player2 else None,
                'is_bye': player1 is None or player2 is None,
            }
            
            # Auto-advance BYEs
            if match['is_bye']:
                match['winner_id'] = (player1 or player2).player_id
                match['status'] = 'completed'
            else:
                match['status'] = 'pending'
            
            matches.append(match)
            match_num += 1
        
        # Generate subsequent round shells
        remaining = bracket_size // 2
        while remaining > 1:
            round_num += 1
            for i in range(remaining // 2):
                matches.append({
                    'round': round_num,
                    'match_number': match_num,
                    'player1_id': None,  # TBD
                    'player2_id': None,
                    'status': 'pending'
                })
                match_num += 1
            remaining //= 2
        
        return matches
    
    def _standard_seeding(self, size: int) -> List[int]:
        """
        Standard tournament seeding placement.
        Ensures: 1 vs size, 2 vs size-1, etc.
        Distributed so top seeds are on opposite sides of bracket.
        
        Example for 8:
        Match 1: seed 1 vs seed 8
        Match 2: seed 4 vs seed 5
        Match 3: seed 2 vs seed 7
        Match 4: seed 3 vs seed 6
        """
        if size == 2:
            return [0, 1]
        
        half = self._standard_seeding(size // 2)
        result = []
        for pos in half:
            result.append(pos)
            result.append(size - 1 - pos)
        
        return result


class SwissPairingEngine:
    """
    Swiss-system tournament pairing (Monrad system).
    
    Rules:
    1. Players with same score are paired together
    2. No rematch (players don't play same opponent twice)
    3. Color balance (in chess: alternate black/white)
    4. Seeding considered within score groups
    """
    
    def generate_round_pairings(self, standings: List[dict], 
                                 previous_matches: set) -> List[tuple]:
        """
        Generate pairings for next Swiss round.
        
        Algorithm:
        1. Group players by score
        2. Within each group, sort by rating
        3. Pair top half vs bottom half
        4. Handle conflicts (previous matches) by swapping
        """
        # Group by score
        score_groups = {}
        for player in standings:
            score = player['score']
            score_groups.setdefault(score, []).append(player)
        
        # Sort groups by score (highest first)
        sorted_scores = sorted(score_groups.keys(), reverse=True)
        
        pairings = []
        floaters = []  # Odd players that float down to next group
        
        for score in sorted_scores:
            group = score_groups[score] + floaters
            floaters = []
            
            # Sort within group by rating
            group.sort(key=lambda p: -p['rating'])
            
            # Split into halves
            mid = len(group) // 2
            top_half = group[:mid]
            bottom_half = group[mid:]
            
            # Handle odd group (one player floats down)
            if len(group) % 2 == 1:
                floaters = [bottom_half.pop()]
            
            # Pair with conflict resolution
            for i, top_player in enumerate(top_half):
                if i < len(bottom_half):
                    opponent = bottom_half[i]
                    pair_key = frozenset([top_player['player_id'], opponent['player_id']])
                    
                    # Check for rematch
                    if pair_key in previous_matches:
                        # Try swapping with next opponent
                        swapped = False
                        for j in range(i + 1, len(bottom_half)):
                            alt_key = frozenset([top_player['player_id'], bottom_half[j]['player_id']])
                            if alt_key not in previous_matches:
                                bottom_half[i], bottom_half[j] = bottom_half[j], bottom_half[i]
                                opponent = bottom_half[i]
                                swapped = True
                                break
                        
                        if not swapped:
                            # Float this player down
                            floaters.append(top_player)
                            continue
                    
                    pairings.append((top_player['player_id'], opponent['player_id']))
        
        # Handle final floater (gets a BYE)
        if floaters:
            pairings.append((floaters[0]['player_id'], None))  # BYE
        
        return pairings
    
    def calculate_swiss_rounds(self, num_participants: int) -> int:
        """Standard Swiss: ceil(log2(N)) rounds to determine winner."""
        return math.ceil(math.log2(num_participants))
```

## 8. Component Optimization

### Redis Cluster Configuration

```yaml
redis_cluster:
  nodes: 100
  shards: 50  # 2 replicas per shard
  
  memory_policy: allkeys-lru
  max_memory_per_node: 64GB
  
  # Sorted set optimization
  zset_max_ziplist_entries: 128
  zset_max_ziplist_value: 64
  
  # Connection optimization  
  tcp_keepalive: 60
  timeout: 0  # Never timeout idle connections
  
  # Persistence (for leaderboard durability)
  appendonly: yes
  appendfsync: everysec
  
  # Cluster-specific
  cluster_node_timeout: 5000
  cluster_allow_reads_when_down: yes  # Serve stale reads
```

### Leaderboard Update Batching

```python
class LeaderboardBatcher:
    """
    Batch score updates to reduce Redis round-trips.
    Instead of updating leaderboard on every score, batch updates every 100ms.
    
    This reduces Redis ops from 500K/s to ~5K batched pipeline calls/s.
    """
    
    BATCH_INTERVAL_MS = 100
    MAX_BATCH_SIZE = 1000
    
    async def process_batch(self, updates: List[dict]):
        pipe = self.redis.pipeline()
        for update in updates:
            pipe.zadd(
                f"leaderboard:global:{update['game_id']}",
                {update['player_id']: update['encoded_score']}
            )
        await pipe.execute()
```

### Matchmaking Performance

```
Optimization: Spatial indexing of rating pool

Instead of O(n²) comparison of all tickets:
1. Bucket players by rating range (buckets of 50 rating points)
2. Only compare adjacent buckets (player in 1500 bucket checks 1450-1550)
3. This reduces comparison from O(n²) to O(n × bucket_size)

Result: Process 100K queued players in <100ms
```

## 9. Observability

### Metrics

```yaml
metrics:
  - name: leaderboard_update_latency_ms
    type: histogram
    labels: [game_id, leaderboard_type]
    buckets: [10, 50, 100, 200, 500, 1000]
  
  - name: leaderboard_query_latency_ms
    type: histogram
    labels: [query_type] # top_k, user_rank, friends
    buckets: [5, 10, 25, 50, 100]
  
  - name: matchmaking_wait_time_seconds
    type: histogram
    labels: [game_mode, region, rating_bucket]
    buckets: [5, 10, 15, 30, 60, 120, 300]
  
  - name: matchmaking_quality_score
    type: histogram
    labels: [game_mode]
    buckets: [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]
  
  - name: tournament_match_completion_rate
    type: gauge
    labels: [tournament_type]
  
  - name: anti_cheat_flags_total
    type: counter
    labels: [flag_type] # speed_hack, impossible_score, suspicious_pattern
  
  - name: score_submissions_per_second
    type: gauge
    labels: [game_id, validated]
  
  - name: concurrent_players
    type: gauge
    labels: [region]
```

### Alerting

```yaml
alerts:
  - name: MatchmakingWaitTooLong
    expr: histogram_quantile(0.95, matchmaking_wait_time_seconds) > 60
    severity: warning
    
  - name: LeaderboardStale
    expr: time() - leaderboard_last_update_timestamp > 5
    severity: critical
    
  - name: AntiCheatSpikeDetected
    expr: rate(anti_cheat_flags_total[5m]) > 100
    severity: warning
    description: "Unusual spike in cheat detections, possible exploit in the wild"
    
  - name: TournamentMatchTimeout
    expr: tournament_pending_matches_duration_seconds > 600
    severity: warning
```

## 10. Considerations

### Seasonal Reset Strategy

```
Soft reset (preferred):
  new_rating = (current_rating - 1500) * decay_factor + 1500
  
  Where decay_factor = 0.75 (compresses ratings toward mean)
  
  A 2000 player → (2000-1500)*0.75 + 1500 = 1875
  A 1200 player → (1200-1500)*0.75 + 1500 = 1275

Hard reset:
  Everyone back to 1500, increase rating_deviation to maximum
  
Hybrid:
  Keep skill rating (hidden MMR), reset visible rank points
  Placement matches determine starting rank tier for new season
```

### Anti-Cheat Architecture

```
Layers:
1. Client-side: Anti-tamper, memory scanning (easy to bypass, defense in depth)
2. Server-side validation: 
   - Physics checks (impossible movement speed)
   - Statistical anomaly (reaction time < human limit)
   - Score rate validation (max possible score per time unit)
3. Replay verification:
   - Replay submitted with score
   - Server re-simulates and verifies score matches
   - Random sampling for expensive verification
4. Behavioral ML:
   - Historical pattern analysis
   - Sudden skill improvement detection
   - Play pattern clustering (bot detection)
```

### Multi-Region Architecture

```
Challenge: Global leaderboard must merge data across regions.

Solution:
- Regional leaderboards: authoritative per-region Redis
- Global leaderboard: asynchronous merge every 1-5 seconds
- Score submission routed to player's home region
- Cross-region tournament: single authoritative region selected

Data flow:
  Score → Regional Redis → Kafka → Global Merger → Global Redis
  Latency: ~2-3s for global board reflection
```

## 11. Failure Scenarios & Recovery

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Redis node failure | Partial leaderboard unavailable | Redis Cluster auto-failover (<5s), read from replica |
| Matchmaking service crash | Players stuck in queue | Queue persisted in Redis, auto-restart picks up |
| Tournament match result lost | Bracket stuck | Match results journaled in Kafka, replay from log |
| Score validation service slow | Delayed leaderboard update | Accept scores optimistically, validate async, rollback if invalid |
| Season reward calculation OOM | Rewards not distributed | Chunked processing, checkpoint progress, retry |
| Rating calculation divergence | Unfair matchmaking | Periodic full recalculation from match history, alerts on deviation |

---
