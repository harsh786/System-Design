# Design Customer Support Chat Platform

## 1. Functional Requirements

- **Live chat widget**: Embeddable widget for websites/apps
- **Multi-channel**: Web chat, mobile, email, social (WhatsApp, FB, Twitter), SMS
- **Agent workspace**: Unified inbox, handle multiple chats simultaneously
- **Intelligent routing**: Route to best agent based on skill, load, language, priority
- **Queue management**: Waitlist with estimated wait time, priority queuing
- **Chatbot/AI**: First-responder bot, FAQ auto-answer, handoff to human
- **Canned responses**: Pre-written templates with variable substitution
- **File sharing**: Images, documents, screenshots between customer and agent
- **Conversation history**: Full history linked to customer profile
- **Internal notes**: Agents add private notes (invisible to customer)
- **Transfer/Escalation**: Transfer between agents, escalate to supervisor
- **Analytics**: CSAT scores, response times, resolution rates, agent performance
- **SLA management**: Track first response time, resolution time against targets
- **Knowledge base**: Searchable articles suggested to agents and customers
- **Co-browsing**: Agent can see customer's screen (with permission)
- **Proactive chat**: Trigger chat based on user behavior (time on page, cart abandon)

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Availability | 99.99% (customer-facing widget) |
| Message delivery | < 200ms between customer and agent |
| First response time | < 30s (business SLA) |
| Queue wait time | Show accurate estimate (±30s) |
| Concurrent chats per agent | 5-8 simultaneous |
| Concurrent conversations | 500K+ platform-wide |
| Bot response time | < 2s for AI responses |
| Scale | 100K+ businesses, 10M+ daily conversations |
| Multi-tenant | Complete data isolation between businesses |

## 3. Capacity Estimation

| Metric | Value |
|---|---|
| Businesses (tenants) | 100K |
| Total agents | 2M |
| Concurrent agents | 500K |
| Daily conversations | 10M |
| Messages/day | 100M (avg 10 msgs/conversation) |
| Messages/sec (avg) | 1,150 |
| Messages/sec (peak) | 5,750 |
| Concurrent open conversations | 500K |
| Bot interactions/day | 30M (many handled without human) |
| File uploads/day | 2M |
| Storage (messages/year) | 100M/day × 2KB × 365 = 73 TB |
| Storage (files/year) | 2M/day × 500KB × 365 = 365 TB |

## 4. Data Modeling

### Database Selection

| Store | Technology | Purpose |
|---|---|---|
| Conversations/Messages | PostgreSQL (partitioned by tenant) | ACID, relational, complex queries |
| Real-time state | Redis | Queue state, routing, presence |
| Bot/AI responses | Vector DB (Pinecone/Pgvector) + LLM | Semantic search, AI responses |
| File storage | S3 | Attachments, screenshots |
| Search | Elasticsearch | Conversation search, knowledge base |
| Analytics | ClickHouse | Agent performance, CSAT trends |
| Event bus | Kafka | Real-time events, integrations |
| Knowledge base | PostgreSQL + Elasticsearch | Articles with full-text search |
| Session/Widget state | Redis | Visitor tracking, proactive triggers |

### Schema

```sql
-- Multi-tenant: tenant_id in every table, row-level security

-- Organizations (tenants)
CREATE TABLE organizations (
    id UUID PRIMARY KEY,
    name VARCHAR(200),
    subdomain VARCHAR(100) UNIQUE,
    plan VARCHAR(20), -- starter, professional, enterprise
    settings JSONB, -- widget config, business hours, auto-replies
    created_at TIMESTAMPTZ
);

-- Agents
CREATE TABLE agents (
    id UUID PRIMARY KEY,
    org_id UUID REFERENCES organizations(id),
    email VARCHAR(255),
    name VARCHAR(100),
    role VARCHAR(20), -- agent, supervisor, admin
    skills TEXT[], -- billing, technical, sales
    languages TEXT[], -- en, es, fr
    max_concurrent_chats INT DEFAULT 5,
    status VARCHAR(20) DEFAULT 'offline', -- online, away, offline
    current_chat_count INT DEFAULT 0,
    created_at TIMESTAMPTZ
);
CREATE INDEX idx_agents_org_status ON agents(org_id, status);

-- Conversations  
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL,
    channel VARCHAR(20), -- web_chat, whatsapp, email, facebook, sms
    customer_id UUID,
    assigned_agent_id UUID,
    team_id UUID,
    status VARCHAR(20) DEFAULT 'open', -- open, pending, resolved, closed
    priority VARCHAR(10) DEFAULT 'normal', -- low, normal, high, urgent
    subject VARCHAR(200),
    tags TEXT[],
    first_response_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    sla_breach BOOLEAN DEFAULT FALSE,
    csat_score SMALLINT, -- 1-5
    metadata JSONB, -- custom fields, page URL, referrer
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);
CREATE INDEX idx_conv_org_status ON conversations(org_id, status, created_at);
CREATE INDEX idx_conv_agent ON conversations(assigned_agent_id, status);
CREATE INDEX idx_conv_customer ON conversations(customer_id, created_at DESC);

-- Messages
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id),
    sender_type VARCHAR(10), -- customer, agent, bot, system
    sender_id UUID,
    content TEXT,
    content_type VARCHAR(20), -- text, image, file, card, quick_reply
    attachments JSONB, -- [{url, type, name, size}]
    internal_note BOOLEAN DEFAULT FALSE, -- visible only to agents
    metadata JSONB,
    created_at TIMESTAMPTZ
);
CREATE INDEX idx_messages_conv ON messages(conversation_id, created_at);

-- Routing Rules
CREATE TABLE routing_rules (
    id UUID PRIMARY KEY,
    org_id UUID,
    priority INT, -- lower = higher priority
    conditions JSONB, -- [{"field": "channel", "op": "eq", "value": "whatsapp"}]
    action JSONB, -- {"assign_to": "team_billing", "priority": "high"}
    active BOOLEAN DEFAULT TRUE
);
```

## 5. High-Level Design

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  CUSTOMER SIDE                      │  AGENT SIDE                            │
│  ┌──────────────────────────────┐   │  ┌────────────────────────────────┐   │
│  │ Chat Widget (JS/iframe)      │   │  │ Agent Dashboard (React SPA)    │   │
│  │ Mobile SDK (iOS/Android)     │   │  │ - Unified inbox                │   │
│  │ WhatsApp/FB/Email integration│   │  │ - Multi-chat view              │   │
│  └──────────────┬───────────────┘   │  │ - Knowledge base sidebar       │   │
│                 │                    │  │ - Customer context panel       │   │
└─────────────────┼────────────────────┘  └────────────────┬───────────────┘   │
                  │                                          │                   
                  ▼                                          ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        GATEWAY & ROUTING                                      │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │ WebSocket GW   │  │   API Gateway   │  │  Channel Connectors          │  │
│  │ (Customer+Agent)│ │  (REST APIs)    │  │  - WhatsApp Business API     │  │
│  │                │  │                 │  │  - Facebook Graph API         │  │
│  │                │  │                 │  │  - Twilio (SMS)               │  │
│  │                │  │                 │  │  - Email (IMAP/SMTP)          │  │
│  └────────┬───────┘  └────────┬────────┘  └──────────────┬───────────────┘  │
└───────────┼────────────────────┼──────────────────────────┼──────────────────┘
            │                    │                           │
            ▼                    ▼                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           CORE SERVICES                                       │
│                                                                               │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │ Conversation   │  │  Routing Engine  │  │  AI/Bot Service              │  │
│  │ Service        │  │  - Skills-based  │  │  - Intent detection          │  │
│  │ - CRUD msgs    │  │  - Load balance  │  │  - FAQ auto-response         │  │
│  │ - State mgmt   │  │  - Priority queue│  │  - Handoff to human          │  │
│  │ - SLA tracking │  │  - Round-robin   │  │  - Suggested replies         │  │
│  └────────────────┘  └─────────────────┘  └──────────────────────────────┘  │
│                                                                               │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │ Queue Manager  │  │  Analytics      │  │  Knowledge Base Service      │  │
│  │ - Wait time est│  │  Service        │  │  - Article CRUD               │  │
│  │ - Position     │  │  - CSAT         │  │  - Semantic search            │  │
│  │ - Priority     │  │  - Response time│  │  - Agent suggestions          │  │
│  │ - Overflow     │  │  - Resolution   │  │  - Customer self-service      │  │
│  └────────────────┘  └─────────────────┘  └──────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design - APIs

### Customer-facing Widget API
```
POST /api/v1/widget/conversations
Headers: X-Widget-Token: "widget_token_for_org"
Request: {"visitor_id": "v_anon_123", "name": "John", "email": "john@example.com", "initial_message": "Need help with billing", "page_url": "https://example.com/pricing", "metadata": {"plan": "pro"}}
Response: {"conversation_id": "conv_abc", "websocket_url": "wss://ws.support.io/customer/conv_abc?token=xxx"}

# WebSocket (Customer)
← {"type": "bot_message", "content": "Hi John! I can help with billing. What specifically do you need?", "quick_replies": ["View invoice", "Change plan", "Talk to human"]}
→ {"type": "message", "content": "I want to change my plan"}
← {"type": "agent_assigned", "agent": {"name": "Sarah", "avatar": "..."}}
← {"type": "message", "sender": "agent", "content": "Hi John! I'd be happy to help you change your plan."}
← {"type": "typing_indicator", "sender": "agent"}
```

### Agent-facing APIs
```
GET /api/v1/agents/me/inbox?status=open&sort=oldest_first
Response: {"conversations": [{...}], "total": 12, "unassigned_queue": 5}

POST /api/v1/conversations/{conv_id}/messages
Request: {"content": "Let me check your account.", "internal_note": false}
Response: {"id": "msg_123", "created_at": "..."}

POST /api/v1/conversations/{conv_id}/assign
Request: {"agent_id": "agent_456", "reason": "transfer to billing specialist"}
Response: {"ok": true}

POST /api/v1/conversations/{conv_id}/resolve
Request: {"resolution_note": "Changed plan to enterprise", "tags": ["billing", "plan_change"]}
Response: {"ok": true, "csat_survey_sent": true}
```

### Routing Engine API (Internal)
```
POST /internal/v1/routing/assign
Request: {"conversation_id": "conv_abc", "org_id": "org_1", "channel": "web_chat", "skills_needed": ["billing"], "language": "en", "priority": "normal"}
Response: {"assigned_agent_id": "agent_789", "estimated_wait_seconds": 15}
```

## 7. Deep Dive - Routing Engine

```
Routing Algorithm:
1. Evaluate routing rules (condition matching)
2. Determine team/skill group
3. Within team, find available agents:
   a. Filter: online AND current_chats < max_concurrent
   b. Score each agent:
      - Skill match: +10 per matching skill
      - Load balance: +5 × (max_concurrent - current_chats) / max_concurrent
      - Language match: +15 if language matches
      - Previous interaction: +20 if customer talked to this agent before
      - CSAT performance: +5 if above team average
   c. Select highest score agent
4. If no agent available: add to priority queue
5. Queue position based on: priority > wait_time > channel_weight

Queue Estimation:
  estimated_wait = queue_position / avg_resolution_rate_per_minute
  Factor in: time of day, agent availability schedule, historical patterns
```

## 8. Optimization

### Multi-tenant Isolation
```
- Database: PostgreSQL with Row-Level Security (RLS)
  SET app.current_org_id = 'org_123';
  Policy: org_id = current_setting('app.current_org_id')
  
- Redis: namespace keys by org_id
  queue:{org_id}:waiting → sorted set
  routing:{org_id}:agents → available agents

- Kafka: shared topics with org_id in message key
  Consumers filter by org_id for tenant-specific processing
  
- API: tenant resolved from widget token or agent JWT
```

### AI/Bot Integration
```
Bot Pipeline:
1. Customer message arrives
2. Intent classification (fine-tuned LLM or BERT model)
3. If confidence > 0.85: auto-respond from knowledge base
4. If confidence 0.5-0.85: suggest response to agent
5. If confidence < 0.5: route to human immediately

Agent Assist (real-time suggestions):
- As customer types, AI suggests responses to agent
- Pull relevant knowledge base articles
- Show customer history and context
- Detect sentiment shift (frustration → escalation suggestion)
```

## 9. Observability

```yaml
Metrics:
  support_conversations_total{org_id, channel, status}
  support_first_response_time_seconds{org_id, quantile}
  support_resolution_time_seconds{org_id, quantile}
  support_queue_wait_time_seconds{org_id, quantile}
  support_queue_depth{org_id, team}
  support_agent_utilization{org_id, agent_id}
  support_csat_score{org_id, average}
  support_bot_deflection_rate{org_id}
  support_sla_breach_total{org_id, sla_type}
  support_messages_per_second{org_id}

Alerts:
  Critical: queue_depth > 100 for > 5min, SLA breach rate > 10%
  Warning: avg wait time > 2min, CSAT < 3.0, bot accuracy < 70%
```

## 10. Considerations

### Key Trade-offs
| Choice | Benefit | Cost |
|---|---|---|
| PostgreSQL over NoSQL | ACID, complex routing queries, RLS multi-tenancy | Horizontal scaling complexity |
| WebSocket for both sides | Real-time both directions, typing indicators | Connection management overhead |
| AI first-responder | Reduces agent load 40-60% | Training data needed, errors frustrate |
| Shared infra multi-tenancy | Cost efficient, easier to manage | Noisy neighbor risk, isolation concerns |

### Assumptions
- 60% of queries handled by bot without human intervention
- Average conversation: 10 messages, 8 minutes
- Agents handle 5 concurrent chats with quality
- Business hours only for most tenants (reduces peak concurrency)
- CSAT survey sent after every resolved conversation
