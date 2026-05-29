# Amazon API Gateway & Service Mesh - Complete Guide

## 1. API Gateway Overview

### What is API Gateway?

Amazon API Gateway is a fully managed service that makes it easy to create, publish, maintain, monitor, and secure APIs at any scale. It acts as the "front door" for applications to access data, business logic, or functionality from backend services.

### Why Use API Gateway?

- **Single Entry Point**: All client requests go through one endpoint, simplifying architecture
- **Routing**: Direct requests to appropriate backend services based on path, method, headers
- **Authentication & Authorization**: Centralized auth (IAM, Cognito, Lambda Authorizer, API Keys)
- **Throttling & Rate Limiting**: Protect backends from traffic spikes
- **Request/Response Transformation**: Modify payloads between client and backend
- **Monitoring & Logging**: CloudWatch metrics, access logs, X-Ray tracing
- **Caching**: Reduce backend load and improve latency
- **SDK Generation**: Auto-generate client SDKs (Java, JavaScript, iOS, Android)
- **API Versioning & Lifecycle Management**: Stages, canary deployments

### Types of API Gateway

| Feature | REST API | HTTP API | WebSocket API |
|---------|----------|----------|---------------|
| **Cost** | $3.50/million requests | $1.00/million requests | $1.00/million messages + $0.25/million connection minutes |
| **Latency** | ~29ms overhead | ~10ms overhead | Persistent connection |
| **Use Case** | Full-featured APIs | Simple proxy, low-latency | Real-time bidirectional |
| **Protocol** | REST/HTTPS | REST/HTTPS | WebSocket (wss://) |
| **Release** | Original (2015) | 2019 (v2) | 2018 |

### REST API vs HTTP API - Detailed Comparison

| Feature | REST API | HTTP API |
|---------|----------|----------|
| **Authorization** | IAM, Cognito, Lambda Authorizer, API Keys | IAM, Cognito, JWT Authorizer, Lambda Authorizer |
| **Request Validation** | ✅ Body, params, headers | ❌ |
| **Request/Response Transformation** | ✅ VTL Mapping Templates | ❌ (parameter mapping only) |
| **Caching** | ✅ Built-in | ❌ |
| **WAF Integration** | ✅ | ❌ |
| **Resource Policies** | ✅ | ❌ |
| **Custom Domain** | ✅ | ✅ |
| **Private Endpoints** | ✅ (VPC Endpoint) | ❌ |
| **API Keys / Usage Plans** | ✅ | ❌ |
| **Canary Deployments** | ✅ | ❌ |
| **X-Ray Tracing** | ✅ | ❌ |
| **Request Throttling** | ✅ (account, stage, route) | ✅ (account, route) |
| **Mutual TLS** | ✅ | ✅ |
| **OpenAPI Import** | ✅ | ✅ |
| **Lambda Proxy** | ✅ | ✅ |
| **HTTP Proxy** | ✅ | ✅ |
| **AWS Service Integration** | ✅ | ❌ |
| **Mock Integration** | ✅ | ❌ |
| **Edge Optimized** | ✅ | ❌ (Regional only) |

**When to use REST API**: Need caching, WAF, request validation, VTL transformations, API keys, or private endpoints.

**When to use HTTP API**: Simple Lambda/HTTP proxy, need lowest latency/cost, JWT authorization is sufficient.

---

## 2. API Gateway Architecture

### Stages

Stages represent different environments for your API deployment:

```
https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/resource
```

- **dev**: Development environment
- **staging**: Pre-production testing
- **prod**: Production traffic

#### Stage Variables

Stage variables are name-value pairs acting as environment variables for your stage:

```
# Define in stage settings
stageVariables.lambdaAlias = "prod"
stageVariables.tableName = "users-prod"
stageVariables.backendUrl = "https://api-prod.example.com"

# Reference in integration
arn:aws:lambda:us-east-1:123456789:function:myFunc:${stageVariables.lambdaAlias}
```

Use cases:
- Point to different Lambda aliases per stage
- Pass configuration to Lambda via context
- Route to different HTTP backends per environment

### Resources and Methods

**Resources** = URL path segments organized hierarchically:
```
/
├── /users
│   ├── GET (list users)
│   ├── POST (create user)
│   └── /{userId}
│       ├── GET (get user)
│       ├── PUT (update user)
│       ├── DELETE (delete user)
│       └── /orders
│           └── GET (get user's orders)
├── /products
│   ├── GET
│   └── /{productId}
│       └── GET
└── /health
    └── GET
```

**Methods** = HTTP verbs: GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD, ANY

### Integration Types

#### 1. Lambda Proxy Integration (AWS_PROXY)

The most common integration. API Gateway passes the entire request as-is to Lambda.

**Request event object:**
```json
{
  "resource": "/users/{userId}",
  "path": "/users/123",
  "httpMethod": "GET",
  "headers": {
    "Authorization": "Bearer eyJhbG...",
    "Content-Type": "application/json"
  },
  "multiValueHeaders": { ... },
  "queryStringParameters": { "status": "active" },
  "multiValueQueryStringParameters": { "status": ["active", "pending"] },
  "pathParameters": { "userId": "123" },
  "stageVariables": { "lambdaAlias": "prod" },
  "requestContext": {
    "accountId": "123456789012",
    "apiId": "abc123",
    "authorizer": {
      "claims": { ... },
      "principalId": "user123"
    },
    "httpMethod": "GET",
    "identity": {
      "sourceIp": "1.2.3.4",
      "userAgent": "Mozilla/5.0..."
    },
    "requestId": "uuid",
    "resourcePath": "/users/{userId}",
    "stage": "prod"
  },
  "body": null,
  "isBase64Encoded": false
}
```

**Required response format:**
```json
{
  "statusCode": 200,
  "headers": {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*"
  },
  "multiValueHeaders": {
    "Set-Cookie": ["cookie1=val1", "cookie2=val2"]
  },
  "body": "{\"userId\": \"123\", \"name\": \"John\"}",
  "isBase64Encoded": false
}
```

> **Important**: `body` must be a string (JSON.stringify for objects). Missing statusCode or malformed response → 502 Bad Gateway.

#### 2. Lambda Custom Integration (AWS)

You define mapping templates to transform request before sending to Lambda and transform response before returning to client.

```velocity
## Integration Request Mapping Template (VTL)
#set($inputRoot = $input.path('$'))
{
  "userId": "$input.params('userId')",
  "action": "getUser",
  "requestedFields": [
    #foreach($field in $inputRoot.fields)
      "$field"#if($foreach.hasNext),#end
    #end
  ]
}
```

```velocity
## Integration Response Mapping Template
#set($inputRoot = $input.path('$'))
{
  "user": {
    "id": "$inputRoot.userId",
    "fullName": "$inputRoot.firstName $inputRoot.lastName",
    "email": "$inputRoot.email"
  },
  "metadata": {
    "requestId": "$context.requestId",
    "timestamp": "$context.requestTime"
  }
}
```

#### 3. HTTP / HTTP Proxy Integration

**HTTP Proxy (HTTP_PROXY)**: Passes request as-is to HTTP endpoint.
```
Client → API Gateway → https://backend.example.com/api/users/123
```

**HTTP Custom (HTTP)**: Uses mapping templates for transformation.
```
# Endpoint URL with path parameters
https://legacy-api.internal.com/v1/customers/{customerId}

# Map API Gateway path param to backend
userId → customerId
```

#### 4. AWS Service Integration (AWS)

Directly invoke AWS services without Lambda:

**SQS - Send Message:**
```
Integration type: AWS
AWS Service: SQS
HTTP Method: POST
Action: SendMessage
Execution Role: arn:aws:iam::123:role/apigw-sqs-role

# Request mapping template:
Action=SendMessage&MessageBody=$input.body&QueueUrl=arn:aws:sqs:us-east-1:123:my-queue
```

**Step Functions - Start Execution:**
```json
// Request mapping template
{
  "input": "$util.escapeJavaScript($input.json('$'))",
  "stateMachineArn": "arn:aws:states:us-east-1:123:stateMachine:myMachine"
}
```

**DynamoDB - PutItem:**
```json
// Request mapping template
{
  "TableName": "Users",
  "Item": {
    "userId": { "S": "$input.path('$.userId')" },
    "name": { "S": "$input.path('$.name')" },
    "createdAt": { "S": "$context.requestTime" }
  }
}
```

#### 5. Mock Integration

Returns a response without sending the request to a backend:

```json
// Integration Request: Request mapping template
{
  "statusCode": 200
}

// Integration Response: Response mapping template (for statusCode 200)
{
  "message": "Mock response",
  "users": [
    {"id": "1", "name": "Test User"},
    {"id": "2", "name": "Another User"}
  ]
}
```

Use cases: API prototyping, testing, CORS preflight (OPTIONS), health checks.

### Request/Response Flow

```
Client Request
    │
    ▼
┌─────────────────────┐
│   Method Request     │  ← Authorization, API Key validation, Request validation
│   (validates input)  │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│ Integration Request  │  ← Mapping template transforms request for backend
│ (transforms request) │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│    Backend Service   │  ← Lambda, HTTP, AWS Service, Mock
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│ Integration Response │  ← Mapping template transforms response
│ (transforms response)│     Maps HTTP status codes to method response
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│   Method Response    │  ← Final response model, headers
│   (returns to client)│
└─────────────────────┘
    │
    ▼
Client Response
```

### Mapping Templates (VTL - Velocity Template Language)

Key VTL variables and utilities:

```velocity
## Input variables
$input.body                        ## Raw request body
$input.json('$.key')               ## JSONPath extraction
$input.path('$.key')               ## Object at JSONPath
$input.params('paramName')         ## Path/query/header param
$input.params().path               ## All path parameters
$input.params().querystring        ## All query parameters
$input.params().header             ## All headers

## Context variables
$context.requestId                 ## API Gateway request ID
$context.identity.sourceIp         ## Client IP
$context.stage                     ## Current stage
$context.authorizer.principalId    ## From Lambda authorizer
$context.authorizer.claims.sub     ## From Cognito authorizer

## Utility functions
$util.escapeJavaScript($string)    ## Escape JS special chars
$util.urlEncode($string)           ## URL encode
$util.urlDecode($string)           ## URL decode
$util.base64Encode($data)          ## Base64 encode
$util.base64Decode($data)          ## Base64 decode

## Control flow
#if($input.path('$.type') == "premium")
  "tier": "premium"
#else
  "tier": "standard"
#end

## Loops
#foreach($item in $input.path('$.items'))
  {
    "id": "$item.id",
    "name": "$item.name"
  }#if($foreach.hasNext),#end
#end
```

### Models (JSON Schema Validation)

Define expected request/response structure:

```json
{
  "$schema": "http://json-schema.org/draft-04/schema#",
  "title": "CreateUserRequest",
  "type": "object",
  "required": ["email", "name"],
  "properties": {
    "email": {
      "type": "string",
      "format": "email",
      "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
    },
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 100
    },
    "age": {
      "type": "integer",
      "minimum": 0,
      "maximum": 150
    },
    "role": {
      "type": "string",
      "enum": ["admin", "user", "moderator"]
    }
  },
  "additionalProperties": false
}
```

When validation fails → 400 Bad Request with error message.

---

## 3. Authentication & Authorization

### IAM Authorization

Uses AWS Signature Version 4 (SigV4) to sign requests.

```
# Request header
Authorization: AWS4-HMAC-SHA256
  Credential=AKIAIOSFODNN7EXAMPLE/20230101/us-east-1/execute-api/aws4_request,
  SignedHeaders=host;x-amz-date,
  Signature=calculated_signature
```

**Use cases:**
- Service-to-service communication within AWS
- Cross-account API access (with resource policies)
- CLI/SDK access

**Cross-account access:**
1. API Resource Policy allows account B
2. Account B creates IAM role with `execute-api:Invoke` permission
3. Account B signs request with SigV4

```json
// Resource Policy for cross-account
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::222222222222:root"
      },
      "Action": "execute-api:Invoke",
      "Resource": "arn:aws:execute-api:us-east-1:111111111111:abc123/*"
    }
  ]
}
```

### Lambda Authorizer (Custom Authorizer)

#### Token-Based Authorizer

Receives token from `Authorization` header:

```javascript
// Lambda Authorizer Function
exports.handler = async (event) => {
  const token = event.authorizationToken; // "Bearer eyJhbG..."
  const methodArn = event.methodArn;

  try {
    // Validate JWT token
    const decoded = jwt.verify(token.replace('Bearer ', ''), SECRET_KEY);

    return generatePolicy(decoded.sub, 'Allow', methodArn, {
      userId: decoded.sub,
      email: decoded.email,
      role: decoded.role
    });
  } catch (err) {
    return generatePolicy('user', 'Deny', methodArn);
    // Or throw 'Unauthorized' for 401
  }
};

function generatePolicy(principalId, effect, resource, context = {}) {
  return {
    principalId: principalId,
    policyDocument: {
      Version: '2012-10-17',
      Statement: [{
        Action: 'execute-api:Invoke',
        Effect: effect,
        Resource: resource  // or "*" for broad access
      }]
    },
    context: context,  // Available in integration as $context.authorizer.key
    usageIdentifierKey: context.apiKey  // Optional: for usage plan tracking
  };
}
```

#### Request-Based Authorizer

Receives headers, query strings, stage variables, and context:

```javascript
exports.handler = async (event) => {
  // event.headers, event.queryStringParameters,
  // event.pathParameters, event.stageVariables, event.requestContext
  const apiKey = event.headers['x-api-key'];
  const clientId = event.queryStringParameters.clientId;
  const sourceIp = event.requestContext.identity.sourceIp;

  // Multi-factor authorization logic
  if (isValidClient(clientId) && isAllowedIp(sourceIp)) {
    return generatePolicy(clientId, 'Allow', event.methodArn);
  }
  return generatePolicy(clientId, 'Deny', event.methodArn);
};
```

#### Caching

- **TTL**: 0 seconds (no caching) to 3600 seconds (1 hour)
- **Default**: 300 seconds
- **Cache key**: Token value (token-based) or all identity sources (request-based)
- **Impact**: Reduces Lambda invocations and latency
- **Caution**: Cached policy applies to all methods if Resource is wildcarded

### Cognito User Pool Authorizer

API Gateway validates JWT tokens from Cognito directly (no Lambda needed):

```yaml
# API Gateway configuration
Authorizer:
  Type: COGNITO_USER_POOLS
  ProviderARNs:
    - arn:aws:cognito-idp:us-east-1:123:userpool/us-east-1_abc123
  IdentitySource: method.request.header.Authorization
```

**Flow:**
1. User authenticates with Cognito → receives ID/Access token
2. Client sends token in Authorization header
3. API Gateway validates token signature, expiration, issuer, audience
4. If valid, extracts claims → accessible via `$context.authorizer.claims.sub`

**OAuth Scopes** (Access token only):
```
# Define scopes on method
Authorization Scopes: read:users, write:users

# Token must contain matching scopes
```

### API Keys + Usage Plans

**API Key**: A unique alphanumeric string distributed to API consumers.

**Usage Plan** defines:
- **Throttle**: Rate (requests/second) + Burst
- **Quota**: Max requests per day/week/month

```
Usage Plan: "Premium"
├── Throttle: 100 RPS, 200 burst
├── Quota: 1,000,000 requests/month
└── Associated API Keys:
    ├── key-customer-A
    ├── key-customer-B
    └── key-customer-C

Usage Plan: "Free Tier"
├── Throttle: 10 RPS, 20 burst
├── Quota: 10,000 requests/month
└── Associated API Keys:
    └── key-free-user-1
```

> **Note**: API Keys are NOT for authorization. They're for tracking and throttling. Combine with IAM/Lambda Authorizer/Cognito for auth.

**Header**: `x-api-key: abc123def456`

### Resource Policies

JSON policies attached to the API for access control:

```json
// IP Whitelist
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Deny",
    "Principal": "*",
    "Action": "execute-api:Invoke",
    "Resource": "arn:aws:execute-api:us-east-1:123:abc123/*",
    "Condition": {
      "NotIpAddress": {
        "aws:SourceIp": ["203.0.113.0/24", "198.51.100.0/24"]
      }
    }
  }]
}
```

```json
// VPC Endpoint Restriction (Private API)
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": "*",
    "Action": "execute-api:Invoke",
    "Resource": "arn:aws:execute-api:us-east-1:123:abc123/*",
    "Condition": {
      "StringEquals": {
        "aws:sourceVpce": "vpce-0123456789abcdef0"
      }
    }
  }]
}
```

### Mutual TLS (mTLS)

Client must present a valid certificate for authentication:

1. **Create truststore**: Upload CA certificate bundle to S3
2. **Configure custom domain** with mutual TLS:
   ```
   Truststore URI: s3://my-bucket/truststore.pem
   Truststore Version: (optional specific version)
   ```
3. Client includes certificate in TLS handshake
4. API Gateway validates against truststore
5. Certificate info available in `$context.identity.clientCert`

### OAuth 2.0 / JWT Authorizer (HTTP API Only)

```yaml
# Native JWT validation - no Lambda needed
JwtAuthorizer:
  Issuer: "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_abc123"
  Audience:
    - "3n4b5urk1ft4fl3mg5e62d9ado"
  IdentitySource: "$request.header.Authorization"
  AuthorizationScopes:
    - "read:data"
    - "write:data"
```

Works with any OIDC-compliant provider (Auth0, Okta, Azure AD, Cognito).

---

## 4. Throttling & Rate Limiting

### Throttle Hierarchy

```
Account Level (hard limit)
│   Default: 10,000 RPS steady-state, 5,000 burst
│   Can request increase via AWS Support
│
├── Stage Level
│   Override per stage (e.g., prod: 5000 RPS, dev: 100 RPS)
│
├── Route/Method Level
│   Override per specific method (e.g., POST /orders: 1000 RPS)
│
└── Usage Plan Level (per API Key)
    Per-key throttle (e.g., key-A: 100 RPS, key-B: 50 RPS)
```

### Token Bucket Algorithm

```
Bucket capacity = Burst limit
Refill rate = Steady-state rate (RPS)

Example: 10,000 RPS steady-state, 5,000 burst
- Bucket holds up to 5,000 tokens
- Refills at 10,000 tokens/second
- Each request consumes 1 token
- If bucket empty → 429 Too Many Requests
```

### 429 Too Many Requests

Response when throttled:
```json
{
  "message": "Too Many Requests"
}
// Headers:
// Retry-After: 1
// x-amzn-ErrorType: TooManyRequestsException
```

### Handling Throttling

1. **Exponential Backoff with Jitter**:
   ```javascript
   const delay = Math.min(maxDelay, baseDelay * Math.pow(2, attempt)) 
                 + Math.random() * jitter;
   ```

2. **Client-side Caching**: Cache responses to reduce API calls

3. **Request Queuing**: Buffer requests with SQS, process at sustainable rate

4. **Request Aggregation**: Batch multiple operations into single requests

5. **CDN/Cache Layer**: CloudFront in front of API Gateway for cacheable responses

---

## 5. Caching

### Configuration

- **Available on**: REST API only (not HTTP API)
- **Scope**: Per stage, optionally per method override
- **Capacity**: 0.5 GB, 1.6 GB, 6.1 GB, 13.5 GB, 28.4 GB, 58.2 GB, 118 GB, 237 GB
- **TTL**: 0 to 3600 seconds (default: 300s)
- **Encryption**: Optional at-rest encryption

### Cache Key Parameters

By default, cache key = full request URL (resource path + query strings). Customize:

```
Cache Key Parameters:
- Query strings: ?status=active&page=1 (include specific params)
- Headers: Accept-Language, X-Custom-Header
- Stage variables (for multi-tenant)
```

### Cache Invalidation

**Client-side** (requires `execute-api:InvalidateCache` IAM permission):
```
Cache-Control: max-age=0
```

**Console**: "Flush entire stage cache" button

**Per-key invalidation**: Not directly supported; use short TTL or flush all

**Require authorization for invalidation**:
```
Settings → Require authorization for cache control: YES
# Unauthorized invalidation requests are handled based on 
# "Unauthorized request handling" setting:
# - FAIL_WITH_403: Return 403
# - SUCCEED_WITH_RESPONSE_HEADER: Ignore header, serve from cache
# - SUCCEED_WITHOUT_RESPONSE_HEADER: Ignore header, serve from cache (no header)
```

### Cost

| Cache Size | Hourly Cost | Monthly (approx) |
|-----------|-------------|-------------------|
| 0.5 GB | $0.020 | $14.40 |
| 1.6 GB | $0.038 | $27.36 |
| 6.1 GB | $0.200 | $144.00 |
| 13.5 GB | $0.250 | $180.00 |
| 28.4 GB | $0.500 | $360.00 |
| 58.2 GB | $1.000 | $720.00 |
| 118 GB | $1.900 | $1,368.00 |
| 237 GB | $3.800 | $2,736.00 |

---

## 6. Advanced Features

### Custom Domain Names

Map `api.example.com` instead of `abc123.execute-api.us-east-1.amazonaws.com`:

**Setup:**
1. Register domain in Route 53 (or any DNS provider)
2. Request ACM certificate for domain (must be in `us-east-1` for Edge-optimized, same region for Regional)
3. Create custom domain in API Gateway
4. Add base path mapping: `/v1` → API + Stage
5. Create Route 53 alias record → API Gateway domain name

```
api.example.com/v1/users → REST API (prod stage) /users
api.example.com/v2/users → REST API v2 (prod stage) /users
```

**Endpoint types:**
- **Edge-optimized**: CloudFront distribution (cert in us-east-1)
- **Regional**: Direct regional endpoint (cert in same region)

### Canary Deployments

Test new deployment with percentage of traffic:

```
Production Stage
├── Main deployment (95% traffic) → Current stable version
└── Canary deployment (5% traffic) → New version

# Monitor canary metrics separately
# If healthy → Promote canary (100% traffic to new version)
# If errors → Rollback (delete canary)
```

Settings:
- Canary percentage: 0.0 to 100.0
- Stage variables can differ between canary and main
- Canary has its own CloudWatch metrics and access logs

### Request Validation

Validate before hitting backend (fail fast):

```
Validator Options:
├── Validate body (JSON Schema model)
├── Validate request parameters (query strings, headers, path params)
└── Validate body AND parameters
```

Invalid request → `400 Bad Request`:
```json
{
  "message": "Invalid request body"
}
```

### CORS (Cross-Origin Resource Sharing)

For browser-based clients calling APIs from different origins:

**Manual setup (REST API):**
1. Create OPTIONS method on resource
2. Add Mock integration
3. Return CORS headers in method response:

```
Access-Control-Allow-Origin: https://example.com
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization, X-Api-Key
Access-Control-Max-Age: 86400
```

> **Lambda Proxy gotcha**: With Lambda proxy integration, Lambda must return CORS headers in its response. API Gateway does NOT add them automatically.

### Binary Media Support

Handle non-text payloads (images, PDFs, protobuf):

```
Settings → Binary Media Types:
- image/png
- image/jpeg
- application/pdf
- application/octet-stream
- */* (all types)
```

Client must set:
- `Content-Type` header matching binary type
- `Accept` header matching binary type
- API Gateway base64 encodes/decodes automatically with proxy integration

### VPC Links

Access private resources (ALB, NLB, ECS, EC2) in VPC:

```
Client → API Gateway → VPC Link → NLB → Private resources in VPC

REST API: VPC Link → NLB (Network Load Balancer) only
HTTP API: VPC Link → ALB, NLB, or Cloud Map service
```

**Setup (REST API):**
1. Create NLB in target VPC
2. Create VPC Link pointing to NLB
3. Configure integration to use VPC Link
4. Set endpoint URL to NLB DNS name

### WAF Integration (REST API only)

Attach AWS WAF Web ACL to protect API:

**Common rules:**
- Rate-based rules (DDoS protection)
- IP reputation lists
- SQL injection protection
- XSS protection
- Geo-blocking
- Bot control
- Custom rules (header inspection, body size limits)

### Private APIs

Accessible only from within your VPC via VPC Interface Endpoint:

```
1. Create VPC Endpoint for execute-api service
2. Create API with endpoint type: PRIVATE
3. Add Resource Policy restricting to VPC endpoint
4. Access: https://{api-id}.execute-api.{region}.amazonaws.com/{stage}
   (resolves only within VPC via endpoint)
```

Or use endpoint-specific DNS:
```
https://{vpce-id}.execute-api.{region}.vpce.amazonaws.com/{stage}
# With Header: Host: {api-id}.execute-api.{region}.amazonaws.com
```

---

## 7. WebSocket API

### Overview

Persistent bidirectional communication between client and server.

```
wss://{api-id}.execute-api.{region}.amazonaws.com/{stage}
```

### Routes

| Route | Trigger | Use Case |
|-------|---------|----------|
| `$connect` | Client connects | Auth, store connectionId in DynamoDB |
| `$disconnect` | Client disconnects | Cleanup connectionId from storage |
| `$default` | No matching route | Fallback handler |
| Custom routes | Message action field | Business logic (e.g., "sendMessage", "joinRoom") |

**Route selection expression**: `$request.body.action`

```json
// Client sends:
{ "action": "sendMessage", "roomId": "123", "text": "Hello" }
// → Routed to "sendMessage" route
```

### Connection Management

```javascript
// Store connection on $connect
const AWS = require('aws-sdk');
const ddb = new AWS.DynamoDB.DocumentClient();

exports.connectHandler = async (event) => {
  const connectionId = event.requestContext.connectionId;
  await ddb.put({
    TableName: 'WebSocketConnections',
    Item: { connectionId, connectedAt: Date.now() }
  }).promise();
  return { statusCode: 200 };
};

// Send message back to client via @connections API
const apigw = new AWS.ApiGatewayManagementApi({
  endpoint: `https://${event.requestContext.domainName}/${event.requestContext.stage}`
});

await apigw.postToConnection({
  ConnectionId: targetConnectionId,
  Data: JSON.stringify({ message: 'Hello from server' })
}).promise();

// Disconnect a client
await apigw.deleteConnection({
  ConnectionId: connectionId
}).promise();

// Get connection info
const info = await apigw.getConnection({
  ConnectionId: connectionId
}).promise();
// Returns: connectedAt, identity (sourceIp, userAgent), lastActiveAt
```

### Use Cases

- **Chat applications**: Real-time messaging between users
- **Live dashboards**: Push metrics/status updates
- **Gaming**: Real-time game state synchronization
- **Notifications**: Push alerts without polling
- **Collaborative editing**: Real-time document collaboration
- **Financial tickers**: Live price updates

---

## 8. Monitoring

### CloudWatch Metrics

| Metric | Description | Statistic |
|--------|-------------|-----------|
| `Count` | Total API requests | Sum |
| `4XXError` | Client-side errors (400-499) | Sum, Average |
| `5XXError` | Server-side errors (500-599) | Sum, Average |
| `Latency` | Total time (Gateway receives → returns response) | Average, p50, p90, p99 |
| `IntegrationLatency` | Time spent in backend | Average, p50, p90, p99 |
| `CacheHitCount` | Requests served from cache | Sum |
| `CacheMissCount` | Requests not in cache | Sum |

**Dimensions**: ApiName, Method, Resource, Stage

**Key formula**: `Latency - IntegrationLatency = API Gateway overhead`

### Access Logging

Custom format (JSON recommended):

```json
{
  "requestId": "$context.requestId",
  "ip": "$context.identity.sourceIp",
  "caller": "$context.identity.caller",
  "user": "$context.identity.user",
  "requestTime": "$context.requestTime",
  "httpMethod": "$context.httpMethod",
  "resourcePath": "$context.resourcePath",
  "status": "$context.status",
  "protocol": "$context.protocol",
  "responseLength": "$context.responseLength",
  "integrationLatency": "$context.integrationLatency",
  "latency": "$context.responseLatency"
}
```

**Destination**: CloudWatch Logs (log group per stage)

### Execution Logging

Detailed logs showing full request/response flow:
- Request headers and body
- Authorization result
- Integration request/response
- Mapping template output
- Method response

> **Warning**: Execution logging can be expensive and include sensitive data. Use only for debugging, not production.

### X-Ray Tracing

Enable Active Tracing on the stage:
- Traces requests through API Gateway → Lambda → downstream services
- Visualize latency bottlenecks
- Track errors across distributed services
- Add custom subsegments in Lambda for granular tracing

---

## 9. Service Mesh Concepts

### What is a Service Mesh?

A **dedicated infrastructure layer** for handling service-to-service communication. It makes communication reliable, secure, and observable without changing application code.

```
Traditional:  Service A ──────────── Service B
                        (direct call)

With Mesh:    Service A → Proxy A ──── Proxy B → Service B
              (app)      (sidecar)    (sidecar)  (app)
```

### Why Service Mesh?

| Concern | Without Mesh | With Mesh |
|---------|-------------|-----------|
| **Observability** | Manual instrumentation | Automatic metrics, traces, logs |
| **Security** | App-level TLS implementation | Automatic mTLS everywhere |
| **Traffic Management** | App-level retry/timeout | Declarative routing, retries |
| **Resilience** | Implement circuit breakers in code | Configurable circuit breaking |
| **Canary/Blue-Green** | Load balancer config | Weighted routing policies |
| **Access Control** | Per-service auth logic | Mesh-level policies |

### Sidecar Proxy Pattern

Each service instance has a companion proxy (typically Envoy):

```
┌─────────────────────────────┐
│         Pod / Task          │
│                             │
│  ┌─────────┐  ┌─────────┐  │
│  │   App   │  │  Envoy  │  │
│  │Container│──│  Proxy  │──── Network
│  │         │  │(sidecar)│  │
│  └─────────┘  └─────────┘  │
│                             │
└─────────────────────────────┘

- All inbound/outbound traffic goes through Envoy
- App communicates on localhost → Envoy handles routing
- Zero application code changes
```

### Data Plane vs Control Plane

**Data Plane** (Envoy proxies):
- Handles every network request
- Load balancing, health checking, routing
- mTLS termination/origination
- Metrics collection
- Circuit breaking, retries, timeouts

**Control Plane** (App Mesh / Istio control):
- Configures proxies (pushes routing rules)
- Certificate management
- Service discovery
- Policy enforcement
- Does NOT touch actual traffic

### Service Mesh vs API Gateway

| Aspect | API Gateway | Service Mesh |
|--------|------------|--------------|
| **Traffic type** | North-South (external → internal) | East-West (internal ↔ internal) |
| **Clients** | External consumers, partners | Internal microservices |
| **Focus** | API management, monetization | Service communication |
| **Auth** | OAuth, API keys, JWT | mTLS (identity-based) |
| **Features** | Rate limiting, caching, transformation | Circuit breaking, retries, observability |
| **Deployment** | Centralized | Distributed (sidecar per service) |

**They complement each other:**
```
External Client → API Gateway → Service A → (mesh) → Service B
                  (north-south)              (east-west)
```

---

## 10. AWS App Mesh

### Components

```
┌─────────────────────────────────────────┐
│                  Mesh                     │
│                                          │
│  ┌─────────────────┐                    │
│  │ Virtual Gateway  │ ← Ingress from    │
│  └────────┬────────┘   outside mesh     │
│           │                              │
│  ┌────────▼────────┐                    │
│  │ Virtual Service  │ ← Logical service  │
│  │ (orders-service) │   abstraction      │
│  └────────┬────────┘                    │
│           │                              │
│  ┌────────▼────────┐                    │
│  │ Virtual Router   │ ← Traffic routing  │
│  │                  │   rules            │
│  │  Routes:         │                    │
│  │  - 90% → v1     │                    │
│  │  - 10% → v2     │                    │
│  └──┬──────────┬───┘                    │
│     │          │                         │
│  ┌──▼───┐  ┌──▼───┐                    │
│  │V.Node│  │V.Node│ ← Actual service    │
│  │ (v1) │  │ (v2) │   instances         │
│  └──────┘  └──────┘                     │
│                                          │
└──────────────────────────────────────────┘
```

**Virtual Service**: Abstraction over real services. Other services reference this name.

**Virtual Node**: Represents an actual service (ECS task, EKS pod, EC2 instance). Defines:
- Service discovery (DNS or Cloud Map)
- Listeners (port, protocol, health check)
- Backends (other virtual services this node talks to)
- TLS configuration

**Virtual Router**: Routes traffic to virtual nodes. Contains routes.

**Routes**: Define matching rules and actions:
- Match: path prefix, HTTP method, headers, scheme
- Action: weighted targets (virtual nodes)
- Retry policy, timeout

**Virtual Gateway**: Ingress for traffic entering the mesh from outside.

### Traffic Routing

#### Weighted Routing (Canary)
```yaml
Route:
  Match:
    Prefix: "/"
  Action:
    WeightedTargets:
      - VirtualNode: orders-v1
        Weight: 90
      - VirtualNode: orders-v2
        Weight: 10
```

#### Path-Based Routing
```yaml
Routes:
  - Match:
      Prefix: "/api/v2/"
    Action:
      WeightedTargets:
        - VirtualNode: orders-v2
          Weight: 100
  - Match:
      Prefix: "/api/v1/"
    Action:
      WeightedTargets:
        - VirtualNode: orders-v1
          Weight: 100
```

#### Header-Based Routing
```yaml
Route:
  Match:
    Prefix: "/"
    Headers:
      - Name: "x-canary"
        Match:
          Exact: "true"
  Action:
    WeightedTargets:
      - VirtualNode: orders-canary
        Weight: 100
```

#### Retry Policies
```yaml
RetryPolicy:
  MaxRetries: 3
  PerRetryTimeout:
    Value: 2
    Unit: s
  HttpRetryEvents:
    - server-error      # 5xx
    - gateway-error     # 502, 503, 504
    - client-error      # 409 (conflict)
  TcpRetryEvents:
    - connection-error
```

### Circuit Breaking

```yaml
VirtualNode:
  ConnectionPool:
    Http:
      MaxConnections: 100        # Max concurrent connections
      MaxPendingRequests: 50     # Max queued requests
    Http2:
      MaxRequests: 200           # Max concurrent HTTP/2 requests
    Tcp:
      MaxConnections: 100
    Grpc:
      MaxRequests: 200
```

When limits exceeded → requests fail immediately (503) instead of overwhelming the backend.

### Timeouts

```yaml
Route:
  Timeout:
    PerRequest:
      Value: 30
      Unit: s       # Max time for single request
    Idle:
      Value: 300
      Unit: s       # Max idle time before connection dropped
```

### Health Checks

```yaml
VirtualNode:
  Listeners:
    - PortMapping:
        Port: 8080
        Protocol: http
      HealthCheck:
        Protocol: http
        Path: "/health"
        HealthyThreshold: 3       # Consecutive successes to mark healthy
        UnhealthyThreshold: 2     # Consecutive failures to mark unhealthy
        TimeoutMillis: 5000       # Timeout per check
        IntervalMillis: 10000     # Time between checks
```

### mTLS in App Mesh

```yaml
# Mesh-level (all services)
Mesh:
  Spec:
    EgressFilter:
      Type: ALLOW_ALL  # or DROP_ALL
    ServiceDiscovery:
      IpPreference: IPv4_PREFERRED

# Per Virtual Node TLS
VirtualNode:
  Listeners:
    - Tls:
        Mode: STRICT  # STRICT, PERMISSIVE, DISABLED
        Certificate:
          Acm:
            CertificateArn: arn:aws:acm:...
          # OR File-based:
          File:
            CertificateChain: /certs/ca.pem
            PrivateKey: /certs/key.pem
        Validation:
          Trust:
            Acm:
              CertificateAuthorityArns:
                - arn:aws:acm-pca:...
```

### Observability

App Mesh Envoy proxies automatically emit:

- **X-Ray**: Distributed tracing (configure `ENABLE_ENVOY_XRAY_TRACING=1`)
- **CloudWatch**: Envoy statistics via StatsD/DogStatsD
- **Prometheus**: Native Prometheus metrics endpoint
- **Access Logs**: Envoy access logs to stdout/file
- **Third-party**: Datadog, Jaeger, Zipkin, Lightstep via Envoy config

---

## 11. App Mesh with ECS/EKS

### ECS Integration

**Task Definition with Envoy sidecar:**

```json
{
  "family": "orders-service",
  "networkMode": "awsvpc",
  "proxyConfiguration": {
    "type": "APPMESH",
    "containerName": "envoy",
    "properties": [
      { "name": "IgnoredUID", "value": "1337" },
      { "name": "ProxyIngressPort", "value": "15000" },
      { "name": "ProxyEgressPort", "value": "15001" },
      { "name": "AppPorts", "value": "8080" },
      { "name": "EgressIgnoredIPs", "value": "169.254.170.2,169.254.169.254" }
    ]
  },
  "containerDefinitions": [
    {
      "name": "app",
      "image": "123456789.dkr.ecr.us-east-1.amazonaws.com/orders:latest",
      "portMappings": [{ "containerPort": 8080 }],
      "dependsOn": [{ "containerName": "envoy", "condition": "HEALTHY" }]
    },
    {
      "name": "envoy",
      "image": "840364872350.dkr.ecr.us-east-1.amazonaws.com/aws-appmesh-envoy:v1.25.1.0-prod",
      "essential": true,
      "environment": [
        { "name": "APPMESH_RESOURCE_ARN", "value": "arn:aws:appmesh:us-east-1:123:mesh/my-mesh/virtualNode/orders-vn" }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -s http://localhost:9901/server_info | grep state | grep -q LIVE"],
        "interval": 5,
        "timeout": 2,
        "retries": 3
      },
      "user": "1337"
    }
  ]
}
```

### EKS Integration

**App Mesh Controller** (Kubernetes operator):

```bash
# Install App Mesh Controller
helm repo add eks https://aws.github.io/eks-charts
helm install appmesh-controller eks/appmesh-controller \
  --namespace appmesh-system \
  --set region=us-east-1 \
  --set serviceAccount.create=true
```

**Automatic sidecar injection** via mutating webhook:

```yaml
# Label namespace for injection
apiVersion: v1
kind: Namespace
metadata:
  name: my-app
  labels:
    mesh: my-mesh
    appmesh.k8s.aws/sidecarInjectorWebhook: enabled
---
# Mesh CRD
apiVersion: appmesh.k8s.aws/v1beta2
kind: Mesh
metadata:
  name: my-mesh
spec:
  namespaceSelector:
    matchLabels:
      mesh: my-mesh
---
# Virtual Node CRD
apiVersion: appmesh.k8s.aws/v1beta2
kind: VirtualNode
metadata:
  name: orders-vn
  namespace: my-app
spec:
  podSelector:
    matchLabels:
      app: orders
  listeners:
    - portMapping:
        port: 8080
        protocol: http
  serviceDiscovery:
    awsCloudMap:
      namespaceName: my-app.local
      serviceName: orders
  backends:
    - virtualService:
        virtualServiceRef:
          name: payments-vs
```

### Cross-Cluster Communication

Virtual Gateways enable traffic from outside the mesh:

```yaml
apiVersion: appmesh.k8s.aws/v1beta2
kind: VirtualGateway
metadata:
  name: ingress-gw
spec:
  namespaceSelector:
    matchLabels:
      gateway: ingress
  podSelector:
    matchLabels:
      app: ingress-envoy
  listeners:
    - portMapping:
        port: 8080
        protocol: http
---
apiVersion: appmesh.k8s.aws/v1beta2
kind: GatewayRoute
metadata:
  name: orders-route
spec:
  httpRoute:
    match:
      prefix: "/orders"
    action:
      target:
        virtualService:
          virtualServiceRef:
            name: orders-vs
```

### Service Discovery with Cloud Map

```yaml
VirtualNode:
  ServiceDiscovery:
    AwsCloudMap:
      NamespaceName: "my-app.local"
      ServiceName: "orders"
      Attributes:
        - Key: "ECS_TASK_DEFINITION_FAMILY"
          Value: "orders-service"
```

Cloud Map maintains registry of healthy instances. Envoy discovers endpoints automatically.

---

## 12. Alternatives Comparison

| Feature | AWS App Mesh | Istio | Linkerd |
|---------|-------------|-------|---------|
| **Proxy** | Envoy | Envoy | linkerd2-proxy (Rust) |
| **Performance** | Good | Moderate (heavier) | Excellent (lightweight) |
| **Complexity** | Low-Medium | High | Low |
| **Features** | Core mesh features | Full-featured (most) | Core + extensions |
| **AWS Integration** | Native (ECS, EKS, EC2) | Manual | Manual |
| **Multi-cloud** | AWS only | Yes | Yes |
| **mTLS** | Yes (ACM, file) | Yes (built-in CA) | Yes (automatic) |
| **Traffic Management** | Weighted, path, header | Weighted, fault inject, mirror | Weighted, traffic split |
| **Circuit Breaking** | Connection pools | Yes (outlier detection) | No (relies on retries) |
| **Observability** | X-Ray, CW, Prometheus | Prometheus, Grafana, Jaeger, Kiali | Prometheus, Grafana, tap |
| **Learning Curve** | Medium | Steep | Gentle |
| **Community** | AWS managed | Large (CNCF graduated) | Growing (CNCF graduated) |
| **Control Plane HA** | Managed by AWS | Self-managed (Istiod) | Self-managed |
| **Cost** | Free (pay for compute) | Free OSS (compute cost) | Free OSS (compute cost) |
| **Best For** | AWS-native workloads | Complex multi-cloud | Simple Kubernetes |

---

## 13. Scenario-Based Interview Questions

### Q1: "Design API Gateway for 10M requests/day microservices"

**Answer:**
```
10M/day = ~116 RPS average, ~350 RPS peak (3x)

Architecture:
- HTTP API (cost: $10/day vs $35/day REST) if features sufficient
- If need caching/WAF → REST API with caching enabled
- CloudFront in front for global distribution + edge caching
- Separate APIs per domain (orders-api, users-api) or single with resources
- Lambda authorizer with caching (300s TTL) for auth
- Usage plans for different consumer tiers
- VPC Link to private ALB for internal services
- CloudWatch dashboards + alarms on 5XX and latency p99
- X-Ray for distributed tracing

Cost estimate (REST API):
- Requests: 10M × $3.50/M = $35/day = ~$1,050/month
- Cache (6.1 GB): $144/month
- Data transfer: variable
- Total: ~$1,200-1,500/month
```

### Q2: "API throttled (429) - troubleshoot and resolve"

**Answer:**
```
Diagnosis:
1. Check CloudWatch → Count metric (which stage/method?)
2. Check if account-level (10K RPS) or method-level throttle
3. Check Usage Plan if using API keys
4. Check if burst limit exceeded (short spikes)

Resolution:
- Immediate: Request account limit increase via AWS Support
- Short-term: Enable caching to reduce backend calls
- Method-level: Set higher limits on critical endpoints
- Client-side: Implement exponential backoff + jitter
- Architecture: Put SQS queue for non-real-time operations
- Distribute: CloudFront caching for GET requests
- Shard: Multiple API Gateways behind Route 53 weighted routing
```

### Q3: "Design multi-tenant API authentication"

**Answer:**
```
Approach: Lambda Authorizer + API Keys + Usage Plans

1. Each tenant gets unique API Key → maps to Usage Plan (tier-based throttling)
2. Lambda Authorizer validates JWT token:
   - Extract tenantId from token claims
   - Validate against tenant registry
   - Return context: { tenantId, tier, permissions }
3. Backend receives tenantId via $context.authorizer.tenantId
4. Usage Plans: Free (100 RPS, 10K/day), Pro (1000 RPS, 1M/day), Enterprise (custom)
5. Resource policy: IP whitelist for enterprise tenants
6. Separate stages per environment (not per tenant)
7. Rate limiting: Per-key throttle in usage plan
8. Monitoring: Custom metrics per tenant via access logs
```

### Q4: "Implement rate limiting per customer tier"

**Answer:**
```
Three-tier system:

Usage Plans:
├── Free:       10 RPS / 20 burst / 1,000 requests/day
├── Pro:        100 RPS / 200 burst / 100,000 requests/day
└── Enterprise: 1,000 RPS / 2,000 burst / Unlimited

Implementation:
1. Create 3 Usage Plans with above settings
2. Generate API Key per customer
3. Associate key with appropriate plan
4. Require API Key on all methods (x-api-key header)
5. Lambda Authorizer validates JWT AND checks tier
6. Return usageIdentifierKey from authorizer for custom key mapping
7. Monitor: CloudWatch metrics per plan, alert on approaching quota
8. Self-service: API to check remaining quota (/quota endpoint)
```

### Q5: "Downstream service failing - how does service mesh help?"

**Answer:**
```
Without mesh: Cascading failures, timeouts pile up, entire system degrades

With App Mesh:
1. Circuit Breaking: maxConnections=100, maxPendingRequests=50
   - When limit hit → immediate 503 instead of waiting
   - Prevents thread/connection exhaustion in calling service

2. Retry Policy: maxRetries=3, perRetryTimeout=2s
   - Events: server-error, gateway-error, connection-error
   - Automatic retry on transient failures

3. Timeouts: perRequest=10s
   - Prevents indefinite waits
   - Frees resources quickly

4. Health Checks: every 5s, unhealthyThreshold=2
   - Remove unhealthy nodes from rotation within 10s

5. Traffic Routing: Route away from failing version
   - Shift weight to healthy version: v1=100%, v2=0%

6. Observability: X-Ray traces show exact failure point
   - Envoy metrics: upstream_rq_5xx, upstream_cx_overflow
```

### Q6: "Migrate monolithic API to microservices"

**Answer:**
```
Strangler Fig pattern with API Gateway:

Phase 1: API Gateway as facade
- Deploy API Gateway in front of monolith
- All routes → HTTP proxy → monolith
- No client changes needed

Phase 2: Extract services incrementally
- Identify bounded contexts (users, orders, payments)
- Extract one service at a time
- Reroute specific paths to new microservice:
  /users/* → Lambda/ECS (new)
  /orders/* → Monolith (still)
  /payments/* → Monolith (still)

Phase 3: Service mesh for internal communication
- Deploy App Mesh as services multiply
- mTLS between services
- Independent scaling and deployment

Phase 4: Complete migration
- All routes point to microservices
- Monolith decommissioned
- Canary deployments for each service independently

Key: Never big-bang. One endpoint at a time. Keep monolith running until fully migrated.
```

### Q7: "WebSocket-based real-time notification system design"

**Answer:**
```
Architecture:
Client ←WebSocket→ API Gateway → Lambda ($connect/$disconnect)
                                      ↓
                                  DynamoDB (connections table)

Event source → SNS/EventBridge → Lambda (broadcaster)
                                      ↓
                              @connections API → push to clients

Components:
1. WebSocket API with routes: $connect, $disconnect, subscribe, unsubscribe
2. DynamoDB: connectionId, userId, subscribedTopics, connectedAt
3. $connect Lambda: validate token, store connection
4. $disconnect Lambda: remove connection
5. subscribe route: add topic to connection record
6. Broadcaster Lambda (triggered by events):
   - Query DynamoDB for connections subscribed to topic
   - Batch postToConnection calls
   - Handle stale connections (410 GoneException → delete)

Scaling concerns:
- DynamoDB: GSI on userId, GSI on topic for efficient queries
- Broadcaster: Fan-out with SQS for >1000 connections
- Connection limit: 500 connections/second (request increase)
- Idle timeout: 10 minutes (send ping to keep alive)
- Message size: 128 KB max (chunk larger payloads)
```

### Q8: "Implement circuit breaker pattern with App Mesh"

**Answer:**
```
Configuration on Virtual Node:

ConnectionPool (App Mesh's circuit breaker):
  Http:
    MaxConnections: 100         # Concurrent connections to backend
    MaxPendingRequests: 50      # Queue size when all connections busy
  
When MaxConnections reached:
  - New requests go to pending queue
  
When MaxPendingRequests reached:
  - Immediate 503 response (circuit "open")

Complementary settings:
  Route timeout: 5s per request
  Retry policy: 2 retries, 1s timeout, only on connection-error
  Health check: 5s interval, unhealthyThreshold=2

Monitoring:
  Envoy metrics:
  - upstream_cx_active (current connections)
  - upstream_cx_overflow (rejected by pool)
  - upstream_rq_pending_overflow (rejected from queue)
  
Alert when overflow > 0 → indicates backend pressure

Recovery:
  - Envoy automatically retries when backend healthy
  - No manual "close circuit" needed
  - Health checks restore nodes to rotation

Limitation vs Istio:
  - App Mesh: Connection pool based (preventive)
  - Istio: Outlier detection (reactive, ejects unhealthy hosts)
  - For true outlier detection in App Mesh: rely on health checks
```

### Q9: "API versioning strategy for backward compatibility"

**Answer:**
```
Options with API Gateway:

1. URL Path Versioning (Recommended):
   /v1/users → v1 backend
   /v2/users → v2 backend
   - Separate resources in same API or separate APIs
   - Custom domain base path mappings: api.example.com/v1, /v2

2. Header Versioning:
   Accept: application/vnd.myapi.v2+json
   - Lambda authorizer or integration routing based on header
   - Cleaner URLs but harder to test (can't bookmark)

3. Query Parameter:
   /users?version=2
   - Easy but not RESTful

4. Stage-based (NOT recommended for versioning):
   /dev/users, /prod/users → these are environments, not versions

Implementation with base path mappings:
   Custom Domain: api.example.com
   ├── /v1 → API-A (prod stage)  [maintained, bug fixes only]
   ├── /v2 → API-B (prod stage)  [current]
   └── /v3 → API-C (prod stage)  [beta, canary 10%]

Deprecation strategy:
   - Sunset header: Sunset: Sat, 01 Jan 2025 00:00:00 GMT
   - Deprecation notice in response headers
   - Usage Plan throttle reduction on old versions
   - Monitor v1 traffic → notify customers → shutdown
```

### Q10: "Design API for mobile + web with different rate limits"

**Answer:**
```
Architecture:
- Single API Gateway REST API
- Two Usage Plans: "Mobile" (higher burst for offline sync) and "Web"
- Lambda Authorizer identifies client type from token claims or user-agent

Approach 1: Separate API Keys per platform
  Mobile App → API Key M → Usage Plan: 200 RPS, 500 burst
  Web App → API Key W → Usage Plan: 100 RPS, 200 burst

Approach 2: Lambda Authorizer + context
  - Extract platform from JWT claim or custom header
  - Return context: { platform: "mobile", tier: "premium" }
  - Method-level throttle as baseline
  - Additional DynamoDB-based rate limiting in Lambda for per-user limits

Approach 3: CloudFront + separate origins
  - mobile.api.example.com → CF → API GW (mobile config)
  - web.api.example.com → CF → API GW (web config)
  - Different cache policies per platform

Optimizations for mobile:
  - Longer cache TTL (offline-first patterns)
  - Compressed responses (Accept-Encoding: gzip)
  - Batch endpoints to reduce round trips
  - WebSocket for real-time instead of polling
```

### Q11: "Secure API Gateway from DDoS and abuse"

**Answer:**
```
Defense in depth:

Layer 1 - CloudFront:
  - Absorbs DDoS at edge (AWS Shield Standard included)
  - Geographic restrictions
  - Rate-based rules

Layer 2 - WAF:
  - Rate-based rules: 2000 requests per 5 min per IP
  - SQL injection / XSS managed rules
  - IP reputation lists (AWS managed)
  - Bot control
  - Custom rules: block specific patterns

Layer 3 - API Gateway:
  - Account throttle: 10,000 RPS
  - Stage/method throttle: tighter limits
  - API Keys + Usage Plans per consumer
  - Resource Policy: IP allowlist for known partners

Layer 4 - Lambda Authorizer:
  - Token validation
  - Custom abuse detection logic
  - Check against blocklist

Layer 5 - Backend:
  - Validate all input (defense in depth)
  - Idempotency keys to prevent replay
```

### Q12: "Design cross-region API with failover"

**Answer:**
```
Architecture:

Route 53 (Latency-based routing + health checks)
├── us-east-1: api-east.example.com → API Gateway (Regional)
│   └── Custom Domain: api.example.com (base path /v1)
└── eu-west-1: api-west.example.com → API Gateway (Regional)
    └── Custom Domain: api.example.com (base path /v1)

Failover setup:
1. Deploy API + backends in both regions
2. Custom domain in each region with same name
3. Route 53 latency-based routing with health checks
4. Health check: GET /health on both APIs
5. If primary fails health check → Route 53 routes to secondary

Data considerations:
- DynamoDB Global Tables for shared state
- S3 cross-region replication for assets
- EventBridge global endpoints for event routing
- Aurora Global Database for relational data

Active-Active vs Active-Passive:
- Active-Active: Both regions serve traffic (lower latency)
- Active-Passive: Secondary only on failover (simpler, cheaper)
```

### Q13: "Implement request/response transformation without Lambda"

**Answer:**
```
Use AWS (custom) integration with VTL mapping templates:

Example: Transform REST request to DynamoDB query

Request: GET /users?email=john@example.com

Integration Request mapping template:
{
  "TableName": "Users",
  "IndexName": "email-index",
  "KeyConditionExpression": "email = :email",
  "ExpressionAttributeValues": {
    ":email": { "S": "$input.params('email')" }
  }
}

Integration Response mapping template:
#set($items = $input.path('$.Items'))
{
  "count": $items.size(),
  "users": [
    #foreach($item in $items)
    {
      "userId": "$item.userId.S",
      "email": "$item.email.S",
      "name": "$item.name.S"
    }#if($foreach.hasNext),#end
    #end
  ]
}

Benefits: No Lambda cold start, no Lambda cost, lower latency
Limitations: VTL complexity, harder to debug, limited logic
```

### Q14: "Design API Gateway for multi-region microservices with App Mesh"

**Answer:**
```
                     Route 53 (Latency)
                    /                    \
          Region A (us-east-1)     Region B (eu-west-1)
          ┌──────────────┐         ┌──────────────┐
          │ API Gateway  │         │ API Gateway  │
          │ (Regional)   │         │ (Regional)   │
          └──────┬───────┘         └──────┬───────┘
                 │                         │
          ┌──────▼───────┐         ┌──────▼───────┐
          │ VPC Link     │         │ VPC Link     │
          │ → NLB        │         │ → NLB        │
          └──────┬───────┘         └──────┬───────┘
                 │                         │
          ┌──────▼───────────────────────────────┐
          │          App Mesh (per region)        │
          │                                       │
          │  Virtual Gateway (ingress)            │
          │       ↓                               │
          │  Virtual Router                       │
          │    ├── /orders → orders-vn            │
          │    ├── /users → users-vn              │
          │    └── /payments → payments-vn        │
          │                                       │
          │  Service-to-service: mTLS, retries,   │
          │  circuit breaking, canary deployments  │
          └───────────────────────────────────────┘

Key decisions:
- API Gateway: External auth, throttling, caching
- App Mesh: Internal traffic management, observability
- Cross-region: Data replication, not mesh replication
- Each region is independent mesh (no cross-region mesh)
```

### Q15: "Troubleshoot high latency in API Gateway"

**Answer:**
```
Diagnostic steps:

1. CloudWatch Metrics:
   - Latency (total) vs IntegrationLatency (backend)
   - If Latency >> IntegrationLatency → API GW overhead
   - If IntegrationLatency is high → backend issue

2. Common causes & fixes:

   API Gateway overhead high:
   - Lambda authorizer not cached → enable caching (300s TTL)
   - Request validation complex model → simplify
   - VTL mapping template complex → simplify or use proxy
   - Solution: Switch to HTTP API (10ms vs 29ms overhead)

   Integration latency high:
   - Lambda cold start → Provisioned Concurrency
   - Lambda in VPC → use VPC with NAT (or consider no-VPC)
   - Backend slow → enable API GW caching
   - Large payload transformation → stream/paginate

3. X-Ray trace analysis:
   - Identify exact component adding latency
   - Check for retries, connection timeouts

4. Quick wins:
   - Enable caching (80%+ cache hit ratio for reads)
   - Regional endpoint (not Edge if clients are same-region)
   - HTTP API if features allow
   - Lambda authorizer caching
   - Reduce payload size
```

---

## Summary - Key Points for Interviews

| Topic | Key Numbers |
|-------|-------------|
| Account throttle | 10,000 RPS steady, 5,000 burst |
| REST API cost | $3.50 per million requests |
| HTTP API cost | $1.00 per million requests |
| Cache TTL | 0-3600s (default 300s) |
| Authorizer cache | 0-3600s TTL |
| WebSocket message | 128 KB max |
| WebSocket connection | 2 hours max (idle: 10 min) |
| Payload limit | 10 MB (REST/HTTP API) |
| Integration timeout | 29 seconds max (hard limit) |
| Lambda authorizer | Token-based or Request-based |
| Stages | Not for versioning (use base path mappings) |
| App Mesh proxy | Envoy (managed by AWS) |
| Circuit breaking | Connection pools (not outlier detection) |

**Decision tree:**
```
Need caching/WAF/validation/transformation? → REST API
Simple proxy, cost-sensitive, low latency? → HTTP API
Real-time bidirectional? → WebSocket API
Internal service communication? → App Mesh
External API management? → API Gateway
Both? → API Gateway (north-south) + App Mesh (east-west)
```
