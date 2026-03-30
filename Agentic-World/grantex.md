# Grantex — Delegated Authorization for AI Agents

> **"What OAuth 2.0 is to humans, Grantex is to agents."**

Grantex is an open delegated authorization protocol purpose-built for AI agents. It solves the fundamental question: **How do you let an AI agent act on your behalf — safely, auditably, and revocably?**

GitHub: `mishrasanjeev/grantex`
Docs: `https://docs.grantex.dev`

---

## Table of Contents

1. [The Problem](#the-problem)
2. [What Grantex Is](#what-grantex-is)
3. [Three Core Primitives](#three-core-primitives)
4. [Authorization Flow (7 Steps)](#authorization-flow-7-steps)
5. [Grantex vs OAuth 2.0](#grantex-vs-oauth-20)
6. [Grantex vs MCP Authorization](#grantex-vs-mcp-authorization)
7. [Integration Patterns](#integration-patterns)
   - [Gateway (Zero-Code)](#gateway-zero-code)
   - [Direct REST API](#direct-rest-api)
   - [n8n Integration](#n8n-integration)
   - [LangChain Integration](#langchain-integration)
8. [Credential Vault — Two-Layer Authorization](#credential-vault--two-layer-authorization)
9. [Decentralization Architecture](#decentralization-architecture)
10. [Complete Code Example: LangChain + Google Calendar](#complete-code-example-langchain--google-calendar)
11. [SDKs and Packages](#sdks-and-packages)
12. [Key Properties](#key-properties)

---

## The Problem

Today's AI agents need to interact with external services (Google Calendar, Slack, GitHub, Stripe, etc.) on behalf of users. The current approaches are deeply flawed:

| Problem | Description |
|---------|-------------|
| **Raw API Key Sharing** | Users paste API keys or OAuth tokens directly into agent configs. If the agent is compromised, the attacker gets full account access with no expiry and no scope limits. |
| **No Agent Identity** | Agents are invisible to the authorization system. You can't tell which agent performed which action, audit behavior, or revoke access per-agent. |
| **No Delegation Model** | When Agent A calls Agent B, there's no way to verify that the delegation chain traces back to an actual human's consent. |
| **No Revocation** | Once a token is shared, there's no mechanism to revoke it from a specific agent without rotating it for everything. |

OAuth 2.0 was designed for humans clicking "Allow" in a browser. It assumes a human is always at the keyboard. Agents operate autonomously, chain through other agents, and act at machine speed — OAuth's model doesn't fit.

---

## What Grantex Is

Grantex is an **open protocol** (not just a product) that provides:

- **Cryptographic agent identity** — every agent gets a verifiable DID (Decentralized Identifier)
- **Human-approved, scoped, time-limited permissions** — users grant explicit consent through a plain-language UI
- **Tamper-evident audit trails** — every action is logged in a hash-chained, append-only ledger
- **Instant revocation** — permissions can be revoked in < 1 second via Redis blocklisting
- **Agent-to-agent delegation** — one agent can delegate a subset of its permissions to another, with depth controls

### Architecture Overview

```
┌──────────┐     ┌─────────────┐     ┌──────────────┐
│  Human   │────▶│   Grantex   │────▶│   Service    │
│  (User)  │     │   Server    │     │  (Google,    │
└──────────┘     └──────┬──────┘     │   Slack...)  │
     │                  │            └──────────────┘
     │ Approves         │ Issues
     │ Consent          │ Grant Token
     ▼                  ▼
┌──────────┐     ┌─────────────┐
│  Consent │     │   Agent     │
│    UI    │     │  (LangChain,│
└──────────┘     │   n8n...)   │
                 └─────────────┘
```

---

## Three Core Primitives

### 1. Agent Identity

Every agent receives a cryptographic **DID (Decentralized Identifier)** upon registration:

```
did:grantex:agt_01HXYZ...
```

This identity is:
- Embedded in every grant token the agent receives
- Used to track which agent performed which action
- Verifiable by any service without calling Grantex's servers
- Unique and non-transferable — you can't fake being another agent

### 2. Delegated Grant

A grant is a **human-approved, scoped, time-limited permission token**. It is an RS256-signed JWT containing:

```json
{
  "sub": "harsh@company.com",       // User who approved
  "agt": "did:grantex:agt_01HXYZ",  // Agent receiving permission
  "scp": ["calendar:read", "calendar:write"],  // Allowed scopes
  "exp": 1711843200,                 // Expiry timestamp
  "gid": "grt_9K2mN...",            // Grant ID for revocation
  "iss": "https://grantex.local",   // Issuer
  "aud": "https://api.example.com"  // Target service
}
```

Key properties:
- **User sees plain-language consent**: "Allow Meeting Scheduler to read and create events on your Google Calendar for 8 hours"
- **Offline-verifiable**: Any service can verify the JWT using Grantex's JWKS endpoint without calling back to the server
- **Revocable**: Can be instantly invalidated by grant ID

### 3. Audit Trail

An **append-only, hash-chained log** of every action:

```json
{
  "entryId": "aud_7Xm2...",
  "timestamp": "2026-03-30T14:30:00Z",
  "agentId": "did:grantex:agt_01HXYZ",
  "grantId": "grt_9K2mN...",
  "action": "calendar:write",
  "resource": "event/evt_ABC123",
  "previousHash": "sha256:a4f8c2...",  // Links to previous entry
  "hash": "sha256:b7d3e1..."           // This entry's hash
}
```

Each entry references the previous entry's hash, creating a tamper-evident chain. If anyone modifies a historical entry, all subsequent hashes break — making tampering detectable.

---

## Authorization Flow (7 Steps)

```
 User              Agent             Grantex Server         Service
  │                  │                     │                    │
  │  1. Register     │                     │                    │
  │                  │────────────────────▶│                    │
  │                  │  Agent DID          │                    │
  │                  │◀────────────────────│                    │
  │                  │                     │                    │
  │  2. Authorize    │                     │                    │
  │                  │────────────────────▶│                    │
  │                  │  Consent URL        │                    │
  │                  │◀────────────────────│                    │
  │                  │                     │                    │
  │  3. Approve      │                     │                    │
  │─────────────────────────────────────▶│                    │
  │  (User reviews scopes, clicks Allow) │                    │
  │  Authorization Code                   │                    │
  │◀─────────────────────────────────────│                    │
  │                  │                     │                    │
  │  4. Exchange     │                     │                    │
  │                  │────────────────────▶│                    │
  │                  │  Grant Token (JWT)  │                    │
  │                  │◀────────────────────│                    │
  │                  │                     │                    │
  │  5. Verify       │                     │                    │
  │                  │─────────────────────────────────────▶│
  │                  │  (Service verifies JWT via JWKS)     │
  │                  │  200 OK                               │
  │                  │◀─────────────────────────────────────│
  │                  │                     │                    │
  │  6. Audit        │                     │                    │
  │                  │────────────────────▶│                    │
  │                  │  (Action logged)    │                    │
  │                  │                     │                    │
  │  7. Revoke (optional)                 │                    │
  │─────────────────────────────────────▶│                    │
  │  (Instant revocation via blocklist)   │                    │
```

**Steps explained:**

1. **Register** — Agent registers with Grantex, receives a DID and API key
2. **Authorize** — Agent requests permission for specific scopes, gets a consent URL
3. **Approve** — User reviews the permission request in plain language and clicks "Allow"
4. **Exchange** — Agent exchanges the authorization code for a signed grant token (JWT)
5. **Verify** — Target service verifies the grant token using JWKS (no callback to Grantex needed)
6. **Audit** — Every action is logged to the hash-chained audit trail
7. **Revoke** — User can revoke the grant at any time; takes effect in < 1 second via Redis blocklist

---

## Grantex vs OAuth 2.0

| Dimension | OAuth 2.0 | Grantex |
|-----------|-----------|---------|
| **Identity Model** | Client ID (app-level) | DID per agent instance |
| **Delegation** | Not supported | Agent-to-agent with depth control |
| **Revocation** | Token rotation (slow) | Instant blocklist (< 1s) |
| **Audit** | Access logs only | Hash-chained, tamper-evident trail |
| **Scope Model** | Static | Hierarchical with registry and constraints |
| **Agent-to-Agent** | Not designed for this | First-class with `parentAgt`, `parentGrnt`, `delegationDepth` |
| **Compliance** | Manual implementation | Built-in verifiable consent chain |
| **Offline Verification** | Requires token introspection | JWT + JWKS (fully offline) |

### When to Use Each

- **OAuth 2.0 / OIDC** → User authentication ("who is this human?")
- **Grantex** → Agent authorization ("what can this agent do on behalf of this human?")
- **Both together** → OAuth authenticates the user, Grantex authorizes the agent. The `principalId` in Grantex maps to the user's OAuth identity.

---

## Grantex vs MCP Authorization

MCP (Model Context Protocol) uses transport-level OAuth 2.1 for authorization. Here are the **6 fundamental differentiators**:

### 1. Delegated ≠ Direct

| | MCP | Grantex |
|---|---|---|
| **Model** | Agent authenticates directly (like a user) | Agent carries a delegated grant (acts on behalf of user) |
| **Analogy** | Giving your house key to the contractor | Giving a time-limited key that only opens the garage, logged every time it's used |

### 2. Cryptographic Agent Identity (DID)

MCP doesn't assign identity to agents — the agent is just whatever presents valid OAuth credentials. Grantex gives every agent a unique, cryptographic DID embedded in every token and audit entry.

### 3. Verifiable Consent Chain

When Agent A delegates to Agent B in MCP, there's no cryptographic proof that the delegation traces back to a human's consent. Grantex embeds `parentAgt`, `parentGrnt`, and `delegationDepth` in the JWT — creating a verifiable chain of delegation.

### 4. Two-Layer Credential Isolation (Vault)

MCP: Agent holds the actual service credentials.
Grantex: Agent presents a grant token to the Credential Vault, which returns a short-lived, scoped upstream token. The agent never touches refresh tokens.

### 5. Delegation Depth Control

Grantex enforces maximum delegation depth. If the policy says `maxDepth: 2`, an agent can delegate to one child, but that child cannot delegate further. MCP has no equivalent.

### 6. Offline JWT Verification

MCP requires the server to validate credentials. Grantex grant tokens are self-contained JWTs verifiable via JWKS — no network call needed.

---

## Integration Patterns

### Gateway (Zero-Code)

The **Grantex Gateway** is a reverse proxy that enforces grant tokens without writing any code. Configure via YAML:

```yaml
# gateway.config.yaml
server:
  port: 8080

grantex:
  serverUrl: http://localhost:3001
  jwksUrl: http://localhost:3001/.well-known/jwks.json

routes:
  - path: /api/calendar/**
    upstream: https://www.googleapis.com/calendar/v3
    scopes:
      - calendar:read
      - calendar:write

  - path: /api/email/**
    upstream: https://gmail.googleapis.com
    scopes:
      - email:read
      - email:send
```

**How it works:**

1. Agent sends request to Gateway with `Authorization: Bearer <grant_token>`
2. Gateway verifies the JWT against JWKS
3. Gateway checks that the token's scopes include the required scopes for the route
4. Gateway forwards the request to the upstream service
5. Gateway injects context headers:
   - `X-Grantex-Principal` — the end-user identity
   - `X-Grantex-Agent` — the agent's DID
   - `X-Grantex-GrantId` — the grant ID for audit/revocation

**Run with Docker:**

```bash
docker run -p 8080:8080 \
  -v ./gateway.config.yaml:/etc/grantex/config.yaml \
  grantex/gateway:latest
```

### Direct REST API

For full control, use the Grantex SDK directly:

```javascript
import { Grantex } from '@grantex/sdk';

const grantex = new Grantex({
  apiKey: process.env.GRANTEX_API_KEY,
  baseUrl: 'http://localhost:3001',
});

// Verify a grant token
const result = await grantex.grants.verify(grantToken);
// result = { valid: true, scopes: ['calendar:read'], principal: 'harsh@co.com', agent: 'did:grantex:agt_...' }

// Log an action to the audit trail
await grantex.audit.log({
  grantToken,
  action: 'calendar:read',
  resource: 'events/list',
  metadata: { date: '2026-03-30' },
});
```

### n8n Integration

**Approach 1: Via Gateway (recommended — zero code)**

1. Deploy the Grantex Gateway with route configuration
2. In n8n, use a standard HTTP Request node
3. Point it at the Gateway URL instead of the service directly
4. Pass the grant token in the `Authorization` header

```
n8n HTTP Node → Gateway (verifies token) → Google Calendar API
```

**Approach 2: Via REST API (full control)**

1. Use n8n's HTTP Request node to call the Grantex `/grants/verify` endpoint
2. On success, make the actual API call
3. Use n8n's Code node for custom logic

### LangChain Integration

Package: `@grantex/langchain`

```bash
npm install @grantex/langchain @grantex/sdk
```

**`createGrantexTool(options)`** — Wraps any function as a LangChain tool with Grantex scope enforcement:

```javascript
import { createGrantexTool } from '@grantex/langchain';

const tool = createGrantexTool({
  name: 'check_availability',
  description: 'Check calendar availability',
  grantToken: GRANT_TOKEN,
  requiredScope: 'calendar:read',
  func: async (input) => {
    // Your logic here — only runs if grant token has calendar:read scope
  },
});
```

**`GrantexAuditHandler`** — LangChain callback handler that automatically logs all tool invocations to the Grantex audit trail:

```javascript
import { GrantexAuditHandler } from '@grantex/langchain';

const auditHandler = new GrantexAuditHandler({
  client: grantex,
  agentId: AGENT_ID,
  grantToken: GRANT_TOKEN,
});

// Pass as callback to AgentExecutor
const result = await agentExecutor.invoke(
  { input: 'Book a meeting...' },
  { callbacks: [auditHandler] },
);
```

---

## Credential Vault — Two-Layer Authorization

The **Credential Vault** is the mechanism that lets agents access external services (Google, Slack, GitHub, etc.) **without ever seeing the user's raw credentials**.

### The Three-Layer Reality

```
Layer 1 (One-time Setup):
  User connects Google account to Grantex via standard OAuth
  → Grantex stores the refresh token in encrypted Vault
  → User does this ONCE, not per agent

Layer 2 (Runtime — Agent Request):
  Agent presents Grantex grant token to Vault
  → Vault verifies grant token (scopes, expiry, agent identity)
  → Vault uses stored refresh token to mint a short-lived Google access token
  → Vault narrows the scopes to match the grant token's scopes
  → Returns temporary token to agent

Layer 3 (Agent calls service):
  Agent calls Google Calendar with the temporary token
  → Token expires in ~60 minutes
  → Agent NEVER sees the refresh token
```

### Code Example

```javascript
// Agent calls the Vault at runtime
const credentials = await grantex.vault.getCredentials({
  grantToken: GRANT_TOKEN,     // Agent's Grantex grant token
  provider: 'google-calendar', // Which service adapter to use
});

// Returns:
// {
//   accessToken: "ya29.a0AfH6SM...",   ← ~60 min Google access token
//   expiresAt: "2026-03-30T18:30:00Z",
//   scopes: ["https://www.googleapis.com/auth/calendar.events"],
//   provider: "google-calendar"
// }

// Agent uses this temporary token — never touches the refresh token
const auth = new google.auth.OAuth2();
auth.setCredentials({ access_token: credentials.accessToken });
const calendar = google.calendar({ version: 'v3', auth });
```

### Why This Matters

| Scenario | Without Vault | With Vault |
|----------|---------------|------------|
| Agent compromised | Attacker gets full OAuth refresh token, unlimited access | Attacker gets ~60-min scoped token, limited damage |
| Scope control | Agent has whatever scopes the token has | Double-narrowed: Grantex scopes → Google scopes |
| Credential rotation | Must update every agent | Rotate in Vault once, agents unchanged |
| Audit | No visibility into credential usage | Every credential fetch is audited |

### Scope Narrowing (Twice)

The scopes are narrowed **twice**:

1. **Grantex grant token**: `calendar:read` + `calendar:write`
2. **Vault maps to narrowest Google scope**: `calendar.events` (not `calendar` which includes settings)

The agent gets the minimum permissions possible on both layers.

### Grantex as OAuth Client

**Grantex** is the registered OAuth client with Google — not individual agents. This means:
- Individual agents don't register with Google
- All credential management is centralized in the Vault
- Rotating Google credentials doesn't affect any agent
- One user connection serves all authorized agents

---

## Decentralization Architecture

A common question: **"If Grantex stores tokens in a Credential Vault, isn't it centralized?"**

The answer: the **core protocol is decentralized**. The Credential Vault is **optional infrastructure** that you can self-host.

### What Makes the Protocol Decentralized

| Component | Why It's Decentralized |
|-----------|----------------------|
| **Grant Tokens (JWT)** | Self-contained, offline-verifiable via JWKS. No callback to Grantex needed. |
| **Agent Identity (DID)** | Decentralized Identifiers — not controlled by any central authority |
| **Audit Trail** | Hash-chained and portable. Can be exported, verified independently, stored anywhere |
| **Scope Verification** | Any service can verify scopes from the JWT payload — no Grantex dependency |

### Three Deployment Models

#### Model A: Without Vault (Fully Decentralized)

```javascript
// Agent manages its own service credentials
const grantex = new Grantex({ ... });
const isAllowed = await grantex.grants.verify(GRANT_TOKEN);

// Agent uses its OWN Google credentials
const auth = new google.auth.OAuth2(MY_CLIENT_ID, MY_SECRET);
auth.setCredentials({ access_token: MY_OWN_TOKEN });
const calendar = google.calendar({ version: 'v3', auth });
```

- Agent verifies the grant token (offline via JWKS)
- Agent manages its own upstream credentials
- No central Vault involved
- Trade-off: each agent needs its own service registrations

#### Model B: Self-Hosted Vault (You Control the Infrastructure)

```yaml
# docker-compose.yaml
services:
  grantex-server:
    image: grantex/server:latest
  grantex-vault:
    image: grantex/vault:latest
    volumes:
      - ./vault-keys:/etc/grantex/keys  # Your encryption keys
```

- You run the Vault on your own infrastructure
- Encryption keys never leave your network
- Full control over data, retention, and access
- Same convenience as managed, but you own everything

#### Model C: Managed Vault (Centralized Convenience)

- Use Grantex's hosted Vault service
- Fastest to set up, zero ops overhead
- Trust Grantex with encrypted credential storage
- Acceptable for many use cases, like using Gmail instead of running your own SMTP server

### Analogies

| Protocol (Decentralized) | Convenience Infrastructure (Optional, Centralized) |
|--------------------------|---------------------------------------------------|
| SMTP | Gmail |
| HTTP | AWS / Cloudflare |
| DNS | Cloudflare DNS / Google DNS |
| **Grantex Protocol** | **Hosted Credential Vault** |

The protocol itself is open and decentralized. The hosted services are convenience layers — you can always swap them out or self-host.

---

## Complete Code Example: LangChain + Google Calendar

A full working example of a LangChain agent that books Google Calendar meetings using Grantex for authorization.

### Project Structure

```
meeting-agent/
├── agent/
│   └── calendar-agent.js      # Main agent with 3 tools
├── scripts/
│   ├── register-agent.js       # One-time agent registration
│   └── request-grant.js        # Grant token acquisition
├── .env
└── package.json
```

### Step 1: Register the Agent

```javascript
// scripts/register-agent.js
import { Grantex } from '@grantex/sdk';

const grantex = new Grantex({
  apiKey: process.env.GRANTEX_API_KEY,
  baseUrl: 'http://localhost:3001',
});

const agent = await grantex.agents.register({
  name: 'meeting-scheduler-agent',
  description: 'LangChain agent that checks availability and books Google Calendar meetings',
  scopes: ['calendar:read', 'calendar:write'],
});

console.log('Agent ID:', agent.id);       // agt_01ABC...
console.log('Agent DID:', agent.did);     // did:grantex:agt_01ABC...
console.log('Agent Key:', agent.apiKey);  // Save securely
```

### Step 2: Request a Grant Token

```javascript
// scripts/request-grant.js
import { Grantex } from '@grantex/sdk';

const grantex = new Grantex({
  apiKey: process.env.GRANTEX_API_KEY,
  baseUrl: 'http://localhost:3001',
});

// Start authorization flow — returns a URL for user consent
const authz = await grantex.grants.authorize({
  agentId: 'agt_01ABC...',
  principalId: 'harsh@company.com',
  scopes: ['calendar:read', 'calendar:write'],
  expiresIn: '8h',
  callbackUrl: 'http://localhost:4000/callback',
});

console.log('Send this to user:', authz.consentUrl);
// User clicks the link → reviews permissions → clicks "Allow"
// → Grantex redirects to callbackUrl with authorization code

// Exchange the code for a grant token
const grant = await grantex.grants.exchange({
  authorizationCode: authz.code,
  agentId: 'agt_01ABC...',
});

console.log('Grant Token:', grant.token);  // Save this — it's the agent's permission
```

### Step 3: The Agent (Main File)

```javascript
// agent/calendar-agent.js
import { Grantex } from '@grantex/sdk';
import { createGrantexTool } from '@grantex/langchain';
import { GrantexAuditHandler } from '@grantex/langchain';
import { ChatOpenAI } from '@langchain/openai';
import { createToolCallingAgent, AgentExecutor } from 'langchain/agents';
import { ChatPromptTemplate } from '@langchain/core/prompts';
import { google } from 'googleapis';

// ── Configuration ──────────────────────────────────────
const AGENT_ID = process.env.GRANTEX_AGENT_ID;
const GRANT_TOKEN = process.env.GRANTEX_GRANT_TOKEN;

const grantex = new Grantex({
  apiKey: process.env.GRANTEX_API_KEY,
  baseUrl: 'http://localhost:3001',
});

// ── Credential Vault Helper ────────────────────────────
// Gets a short-lived Google access token via the Vault
// Agent NEVER sees the refresh token
async function getGoogleCalendarClient() {
  const credentials = await grantex.vault.getCredentials({
    grantToken: GRANT_TOKEN,
    provider: 'google-calendar',
  });
  const auth = new google.auth.OAuth2();
  auth.setCredentials({ access_token: credentials.accessToken });
  return google.calendar({ version: 'v3', auth });
}

// ── Tool 1: Check Availability ─────────────────────────
const checkAvailability = createGrantexTool({
  name: 'check_availability',
  description:
    'Check if a specific time slot is available on the calendar. ' +
    'Input: JSON with date (YYYY-MM-DD), time (HH:MM), durationMinutes (number).',
  grantToken: GRANT_TOKEN,
  requiredScope: 'calendar:read',
  func: async (input) => {
    const { date, time, durationMinutes } = JSON.parse(input);
    const calendar = await getGoogleCalendarClient();

    const startTime = new Date(`${date}T${time}:00`);
    const endTime = new Date(startTime.getTime() + durationMinutes * 60000);

    const response = await calendar.freebusy.query({
      requestBody: {
        timeMin: startTime.toISOString(),
        timeMax: endTime.toISOString(),
        items: [{ id: 'primary' }],
      },
    });

    const busySlots = response.data.calendars.primary.busy;
    return JSON.stringify({
      available: busySlots.length === 0,
      requestedSlot: {
        start: startTime.toISOString(),
        end: endTime.toISOString(),
      },
      conflicts: busySlots,
    });
  },
});

// ── Tool 2: Book Meeting ───────────────────────────────
const bookMeeting = createGrantexTool({
  name: 'book_meeting',
  description:
    'Book a meeting on Google Calendar. ' +
    'Input: JSON with title, date (YYYY-MM-DD), time (HH:MM), ' +
    'durationMinutes (number), attendees (array of email strings).',
  grantToken: GRANT_TOKEN,
  requiredScope: 'calendar:write',
  func: async (input) => {
    const { title, date, time, durationMinutes, attendees } = JSON.parse(input);
    const calendar = await getGoogleCalendarClient();

    const startTime = new Date(`${date}T${time}:00`);
    const endTime = new Date(startTime.getTime() + durationMinutes * 60000);

    const event = await calendar.events.insert({
      calendarId: 'primary',
      requestBody: {
        summary: title,
        start: { dateTime: startTime.toISOString() },
        end: { dateTime: endTime.toISOString() },
        attendees: attendees.map((email) => ({ email })),
        reminders: { useDefault: true },
      },
      sendUpdates: 'all',
    });

    return JSON.stringify({
      success: true,
      eventId: event.data.id,
      htmlLink: event.data.htmlLink,
      summary: event.data.summary,
      start: event.data.start.dateTime,
      end: event.data.end.dateTime,
    });
  },
});

// ── Tool 3: List Events ────────────────────────────────
const listEvents = createGrantexTool({
  name: 'list_events',
  description:
    "List today's upcoming calendar events. " +
    'Optional input: JSON with date (YYYY-MM-DD). Defaults to today.',
  grantToken: GRANT_TOKEN,
  requiredScope: 'calendar:read',
  func: async (input) => {
    const { date } = input ? JSON.parse(input) : {};
    const calendar = await getGoogleCalendarClient();

    const targetDate = date ? new Date(date) : new Date();
    const startOfDay = new Date(targetDate.setHours(0, 0, 0, 0));
    const endOfDay = new Date(targetDate.setHours(23, 59, 59, 999));

    const response = await calendar.events.list({
      calendarId: 'primary',
      timeMin: startOfDay.toISOString(),
      timeMax: endOfDay.toISOString(),
      singleEvents: true,
      orderBy: 'startTime',
    });

    const events = response.data.items.map((e) => ({
      title: e.summary,
      start: e.start.dateTime || e.start.date,
      end: e.end.dateTime || e.end.date,
      attendees: e.attendees?.map((a) => a.email) || [],
    }));

    return JSON.stringify({
      date: startOfDay.toISOString().split('T')[0],
      events,
    });
  },
});

// ── Audit Handler ──────────────────────────────────────
// Automatically logs every tool invocation to the audit trail
const auditHandler = new GrantexAuditHandler({
  client: grantex,
  agentId: AGENT_ID,
  grantToken: GRANT_TOKEN,
});

// ── LLM and Agent Setup ────────────────────────────────
const llm = new ChatOpenAI({ model: 'gpt-4o', temperature: 0 });

const prompt = ChatPromptTemplate.fromMessages([
  [
    'system',
    `You are a smart meeting scheduling assistant. You can:
     1. Check calendar availability before booking
     2. Book meetings with attendees
     3. List existing events
     Always check availability before booking. Include all attendees.`,
  ],
  ['human', '{input}'],
  ['placeholder', '{agent_scratchpad}'],
]);

const tools = [checkAvailability, bookMeeting, listEvents];
const agent = createToolCallingAgent({ llm, tools, prompt });
const agentExecutor = new AgentExecutor({ agent, tools, verbose: true });

// ── Run the Agent ──────────────────────────────────────
const result = await agentExecutor.invoke(
  {
    input:
      'Book a 45-minute meeting with alice@company.com ' +
      'tomorrow at 2pm titled "Project Sync"',
  },
  { callbacks: [auditHandler] },
);

console.log('\nAgent Response:', result.output);
```

### Execution Flow

```
User: "Book a 45-min meeting with alice@company.com tomorrow at 2pm"
  │
  ▼
Agent (LangChain) decides to:
  │
  ├─ 1. check_availability (calendar:read)
  │    ├─ createGrantexTool verifies grant token has calendar:read ✓
  │    ├─ Vault returns ~60-min Google access token
  │    ├─ Calls Google FreeBusy API
  │    ├─ Returns: { available: true }
  │    └─ Audit: logged to hash-chained trail
  │
  ├─ 2. book_meeting (calendar:write)
  │    ├─ createGrantexTool verifies grant token has calendar:write ✓
  │    ├─ Vault returns ~60-min Google access token
  │    ├─ Calls Google Events.insert API
  │    ├─ Returns: { success: true, eventId: "...", htmlLink: "..." }
  │    └─ Audit: logged to hash-chained trail
  │
  └─ 3. Agent responds:
       "I've booked 'Project Sync' for tomorrow 2:00-2:45 PM
        with alice@company.com. Calendar invite sent."
```

---

## SDKs and Packages

### Core SDKs

| Package | Language | Description |
|---------|----------|-------------|
| `@grantex/sdk` | TypeScript | Core SDK — grants, agents, vault, audit |
| `grantex` (PyPI) | Python | Core Python SDK |
| `grantex` (Go module) | Go | Core Go SDK |

### Framework Integrations

| Package | Framework | Description |
|---------|-----------|-------------|
| `@grantex/express` | Express.js | Middleware for Express APIs |
| `@grantex/langchain` | LangChain | `createGrantexTool()` + `GrantexAuditHandler` |
| `@grantex/gateway` | Standalone | Zero-code reverse proxy |
| `grantex-fastapi` | FastAPI | Middleware for FastAPI |
| `grantex-crewai` | CrewAI | Integration for CrewAI agents |
| `grantex-django` | Django | Middleware for Django REST |

### Service Provider Adapters

Pre-built adapters for the Credential Vault:

| Service | Adapter ID |
|---------|-----------|
| Google Calendar | `google-calendar` |
| Gmail | `google-gmail` |
| Google Drive | `google-drive` |
| Slack | `slack` |
| GitHub | `github` |
| Stripe | `stripe` |
| Notion | `notion` |
| HubSpot | `hubspot` |
| Salesforce | `salesforce` |
| Linear | `linear` |
| Jira | `jira` |

---

## Key Properties

| Property | Description |
|----------|-------------|
| **Open Protocol** | Not vendor-locked. Self-hostable. Open specification. |
| **Offline Verification** | Grant tokens are JWTs verifiable via JWKS — no server callback needed |
| **Instant Revocation** | < 1 second via Redis blocklist; cascade revocation through delegation trees |
| **Agent-to-Agent Delegation** | First-class support with `parentAgt`, `parentGrnt`, `delegationDepth` claims |
| **Tamper-Evident Audit** | Hash-chained, append-only log — modifying history breaks all subsequent hashes |
| **Scope Narrowing** | Hierarchical scopes narrowed twice (Grantex → Vault → upstream service) |
| **Framework Agnostic** | Works with LangChain, CrewAI, n8n, custom agents, or any HTTP client |
| **Backward Compatible** | Works alongside OAuth 2.0 — uses OAuth for user auth, Grantex for agent auth |

---

## Local Development

Quick start with Docker Compose:

```bash
git clone https://github.com/mishrasanjeev/grantex.git
cd grantex
docker compose up -d
```

This starts:
- **Grantex Server** on `http://localhost:3001`
- **Grantex Dashboard** on `http://localhost:3000`
- **PostgreSQL** database
- **Redis** for revocation blocklist

Seeded developer accounts are available for testing. Verify with:

```bash
curl http://localhost:3001/health
# { "status": "healthy", "version": "0.1.0" }
```

Enable sandbox mode for development:

```yaml
# .env
GRANTEX_SANDBOX=true  # Disables real OAuth flows, uses mock credentials
```
