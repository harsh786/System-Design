# API Design & Governance - Staff Engineer / Architect Level

## Target Level: Staff Engineer / Architect
These problems focus on designing APIs that work at organizational scale -- versioning, evolution, contracts, and governance for hundreds of services and teams.

---

## Problem 1: API Versioning Strategy for 200 Services

**Scenario:** Your organization has 200 services with 2000+ API endpoints. Teams independently deploy 50+ times/day. Problems:
- Breaking changes deployed without consumer awareness
- No standard versioning approach (some use URL, some headers)
- Integration tests catch breaks too late (after deployment)
- API documentation is always stale

### Q1: What versioning strategy would you recommend and why?

```
VERSIONING APPROACHES:

1. URL PATH VERSIONING: /api/v1/users, /api/v2/users
   Pros: Explicit, easy to route, cacheable
   Cons: URL pollution, clients must change URLs
   When: Public APIs, major versions only

2. HEADER VERSIONING: Accept: application/vnd.company.v2+json
   Pros: Clean URLs, content negotiation standard
   Cons: Harder to test (curl), hidden
   When: Internal APIs, fine-grained versioning

3. QUERY PARAMETER: /api/users?version=2
   Pros: Easy to add, visible
   Cons: Pollutes query string, caching issues
   When: Quick prototyping (not recommended for production)

4. NO EXPLICIT VERSIONING (Evolutionary Design):
   Pros: No version coordination needed
   Cons: Requires strict evolution rules
   When: Internal APIs with contract testing

RECOMMENDED FOR LARGE ORGS: Evolutionary Design + Contract Testing

Rules for backward-compatible evolution:
  ✅ ADD new fields (old clients ignore them)
  ✅ ADD new endpoints
  ✅ ADD new optional parameters
  ✅ DEPRECATE fields (keep returning, mark deprecated)
  ❌ NEVER remove fields (until all consumers migrated)
  ❌ NEVER rename fields
  ❌ NEVER change field types
  ❌ NEVER change semantics of existing fields
  ❌ NEVER make optional fields required

When BREAKING CHANGE is unavoidable:
  1. Create new endpoint alongside old
  2. Migrate consumers (track with consumer registry)
  3. Deprecate old endpoint (sunset header)
  4. Remove after all consumers migrated
```

### Q2: How do you implement API evolution in Spring Boot?

```java
// Strategy: Additive changes + deprecation lifecycle

// 1. Adding new fields (always backward-compatible)
public class UserResponse {
    private String id;
    private String name;
    private String email;
    
    // New field added - old clients just ignore it
    @JsonInclude(JsonInclude.Include.NON_NULL)
    private String avatarUrl;  // Added in v2, null for old data
    
    // Deprecated field - still returned, but marked for removal
    @Deprecated(since = "2024-06", forRemoval = true)
    @JsonProperty("fullName")
    private String fullName;  // Use firstName + lastName instead
}

// 2. Sunset header for deprecated endpoints
@RestController
public class UserController {
    
    @GetMapping("/api/users/{id}/profile")
    @Deprecated
    public ResponseEntity<UserProfile> getProfileLegacy(@PathVariable String id) {
        return ResponseEntity.ok()
            .header("Sunset", "Sat, 01 Mar 2025 00:00:00 GMT")
            .header("Deprecation", "true")
            .header("Link", "</api/v2/users/" + id + ">; rel=\"successor-version\"")
            .body(userService.getProfile(id));
    }
    
    @GetMapping("/api/v2/users/{id}")
    public UserDetailResponse getUserDetail(@PathVariable String id) {
        return userService.getUserDetail(id);  // New, richer response
    }
}

// 3. Request/Response evolution with Jackson
@JsonIgnoreProperties(ignoreUnknown = true) // ALWAYS set this
public class CreateUserRequest {
    @NotBlank
    private String name;
    
    @NotBlank
    private String email;
    
    // New optional field - old clients don't send it
    @Nullable
    private String preferredLanguage;  // Defaults to "en" if not provided
}

// 4. API compatibility validation in tests
@SpringBootTest
public class ApiCompatibilityTest {
    
    @Test
    void oldClientRequestStillWorks() {
        // Simulate old client (doesn't send new fields)
        String oldClientPayload = """
            {"name": "John", "email": "john@example.com"}
            """;
        
        webTestClient.post().uri("/api/users")
            .contentType(MediaType.APPLICATION_JSON)
            .bodyValue(oldClientPayload)
            .exchange()
            .expectStatus().isCreated();
    }
    
    @Test
    void oldClientCanReadNewResponse() {
        // New response has extra fields - old client should handle gracefully
        String response = webTestClient.get().uri("/api/users/123")
            .exchange()
            .expectStatus().isOk()
            .returnResult(String.class)
            .getResponseBody()
            .blockFirst();
        
        // Old client model (doesn't know about new fields)
        OldUserResponse oldModel = objectMapper.readValue(response, OldUserResponse.class);
        assertThat(oldModel.getName()).isNotBlank();
        // Should not throw even with unknown fields
    }
}
```

---

## Problem 2: Contract Testing Between Services

### Q3: How do you prevent breaking changes from reaching production?

```
CONTRACT TESTING APPROACH:

Provider (API producer) defines contract
Consumer (API caller) verifies against contract
Both sides test independently → catch breaks before deployment

┌──────────────────────────────────────────────────────────────┐
│  CONTRACT TESTING WITH SPRING CLOUD CONTRACT                  │
│                                                               │
│  ┌─────────────┐     Contract     ┌─────────────────┐       │
│  │  Provider   │ ←──────────────→ │  Consumer        │       │
│  │  (User Svc) │     (shared)     │  (Order Svc)     │       │
│  │             │                   │                  │       │
│  │ Verifies:   │                   │ Verifies:        │       │
│  │ "I produce  │                   │ "I can consume   │       │
│  │  what the   │                   │  what provider   │       │
│  │  contract   │                   │  promised"       │       │
│  │  says"      │                   │                  │       │
│  └─────────────┘                   └─────────────────┘       │
└──────────────────────────────────────────────────────────────┘
```

```java
// Provider side: Define contracts (Groovy DSL or YAML)
// src/test/resources/contracts/user/get_user.groovy

Contract.make {
    description "should return user by ID"
    request {
        method GET()
        url "/api/users/123"
        headers {
            contentType(applicationJson())
        }
    }
    response {
        status OK()
        headers {
            contentType(applicationJson())
        }
        body([
            id: "123",
            name: "John Doe",
            email: "john@example.com",
            // Note: adding avatarUrl later won't break this contract
        ])
    }
}

// Provider verification test (auto-generated)
@SpringBootTest(webEnvironment = RANDOM_PORT)
@AutoConfigureStubRunner
public class UserContractVerifierTest extends UserServiceBase {
    // Spring Cloud Contract auto-generates tests from contracts
    // These tests verify the provider API matches the contract
}

// Consumer side: Use stubs generated from contracts
@SpringBootTest
@AutoConfigureStubRunner(
    ids = "com.example:user-service:+:stubs:8080",
    stubsMode = StubRunnerProperties.StubsMode.REMOTE  // From Artifactory
)
public class OrderServiceContractTest {
    
    @Autowired
    private UserServiceClient userClient;
    
    @Test
    void shouldGetUserFromStub() {
        // Stub is auto-configured from provider's contract
        User user = userClient.getUser("123");
        assertThat(user.getName()).isEqualTo("John Doe");
    }
}

// PACT alternative (consumer-driven contracts)
@ExtendWith(PactConsumerTestExt.class)
@PactTestFor(providerName = "user-service")
public class OrderServicePactTest {
    
    @Pact(consumer = "order-service")
    public RequestResponsePact getUserPact(PactDslWithProvider builder) {
        return builder
            .given("user 123 exists")
            .uponReceiving("a request for user 123")
            .path("/api/users/123")
            .method("GET")
            .willRespondWith()
            .status(200)
            .body(new PactDslJsonBody()
                .stringType("id", "123")
                .stringType("name", "John Doe")
                .stringType("email", "john@example.com"))
            .toPact();
    }
    
    @Test
    @PactTestFor(pactMethod = "getUserPact")
    void testGetUser(MockServer mockServer) {
        UserServiceClient client = new UserServiceClient(mockServer.getUrl());
        User user = client.getUser("123");
        assertThat(user.getName()).isEqualTo("John Doe");
    }
}
```

### Q4: How do you implement contract testing in CI/CD at scale?

```
CI/CD PIPELINE WITH CONTRACT TESTING:

┌─────────────────────────────────────────────────────────────────┐
│  Provider (User Service) Pipeline:                               │
│                                                                   │
│  1. Code change → Run unit tests                                 │
│  2. Generate stubs from contracts                                │
│  3. Run contract verification tests (provider side)              │
│  4. Publish stubs to artifact repository                         │
│  5. Trigger "can-i-deploy" check against all consumers           │
│  6. Deploy if all consumers are compatible                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Consumer (Order Service) Pipeline:                               │
│                                                                   │
│  1. Code change → Run unit tests                                 │
│  2. Download latest provider stubs                               │
│  3. Run consumer contract tests against stubs                    │
│  4. Publish verification results to Pact Broker                  │
│  5. "can-i-deploy" check: Am I compatible with production?       │
│  6. Deploy if compatible                                         │
└─────────────────────────────────────────────────────────────────┘

BREAKING CHANGE DETECTED:
  Provider changes /api/users response → removes "email" field
  1. Provider CI generates new stubs
  2. Consumer CI runs against new stubs → FAILS (expects "email")
  3. Provider deployment BLOCKED ("can-i-deploy" fails)
  4. Provider team notified: "Breaking change affects order-service"
  5. Options:
     a. Provider reverts the breaking change
     b. Provider and consumer coordinate migration
     c. Provider creates new version endpoint
```

---

## Problem 3: API Gateway Governance

### Q5: How do you enforce API standards across 50 teams?

```
API GOVERNANCE FRAMEWORK:

1. API DESIGN STANDARDS (automated enforcement):
   - OpenAPI spec required for every service
   - Linting rules in CI (Spectral, Redocly)
   - Standards include:
     * Naming conventions (camelCase for JSON, kebab-case for URLs)
     * Pagination format (cursor-based for large datasets)
     * Error response format (RFC 7807 Problem Details)
     * Authentication scheme (OAuth2 + JWT)
     * Versioning approach
     * Rate limiting headers

2. API REGISTRY (central catalog):
   - Every API registered with metadata
   - Dependencies tracked (who calls whom)
   - Deprecation lifecycle managed
   - Usage metrics per endpoint

3. API REVIEW PROCESS:
   - New APIs: Design review before implementation
   - Breaking changes: Impact assessment required
   - Automated compatibility checks in PR

Spring Boot Implementation of Standards:

// Standardized error format (RFC 7807)
@ControllerAdvice
public class StandardErrorHandler {
    
    @ExceptionHandler(NotFoundException.class)
    public ResponseEntity<ProblemDetail> handleNotFound(NotFoundException ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
            HttpStatus.NOT_FOUND, ex.getMessage());
        problem.setTitle("Resource Not Found");
        problem.setType(URI.create("https://api.company.com/errors/not-found"));
        problem.setProperty("traceId", MDC.get("traceId"));
        problem.setProperty("timestamp", Instant.now());
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(problem);
    }
    
    @ExceptionHandler(ConstraintViolationException.class)
    public ResponseEntity<ProblemDetail> handleValidation(ConstraintViolationException ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
            HttpStatus.BAD_REQUEST, "Validation failed");
        problem.setTitle("Validation Error");
        problem.setProperty("violations", ex.getConstraintViolations().stream()
            .map(v -> Map.of("field", v.getPropertyPath().toString(), "message", v.getMessage()))
            .toList());
        return ResponseEntity.badRequest().body(problem);
    }
}

// Standardized pagination
public record PageResponse<T>(
    List<T> items,
    String nextCursor,      // Cursor for next page
    boolean hasMore,
    int totalCount          // Optional, expensive for large datasets
) {}

@GetMapping("/users")
public PageResponse<UserResponse> listUsers(
        @RequestParam(required = false) String cursor,
        @RequestParam(defaultValue = "20") @Max(100) int limit) {
    return userService.listUsers(cursor, limit);
}

// Rate limit headers (standard)
@Component
public class RateLimitHeaderFilter implements WebFilter {
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        return chain.filter(exchange)
            .doOnSuccess(v -> {
                exchange.getResponse().getHeaders().add("X-RateLimit-Limit", "1000");
                exchange.getResponse().getHeaders().add("X-RateLimit-Remaining", "999");
                exchange.getResponse().getHeaders().add("X-RateLimit-Reset", "1710500000");
            });
    }
}
```

---

## Problem 4: API Performance at Scale

### Q6: How do you optimize API performance for 100K rps?

```
PERFORMANCE OPTIMIZATION LAYERS:

1. RESPONSE CACHING:
   // HTTP-level caching (client and CDN)
   @GetMapping("/products/{id}")
   public ResponseEntity<Product> getProduct(@PathVariable String id) {
       Product product = productService.getProduct(id);
       return ResponseEntity.ok()
           .cacheControl(CacheControl.maxAge(Duration.ofMinutes(5)).mustRevalidate())
           .eTag(product.getVersion().toString())
           .body(product);
   }
   
   // Conditional requests (304 Not Modified)
   @GetMapping("/products/{id}")
   public ResponseEntity<Product> getProduct(
           @PathVariable String id,
           WebRequest request) {
       Product product = productService.getProduct(id);
       if (request.checkNotModified(product.getVersion().toString())) {
           return null; // 304 Not Modified (no body transferred)
       }
       return ResponseEntity.ok().eTag(product.getVersion().toString()).body(product);
   }

2. RESPONSE COMPRESSION:
   server:
     compression:
       enabled: true
       min-response-size: 1024  # Only compress >1KB
       mime-types: application/json,text/html

3. FIELD SELECTION (reduce payload):
   GET /api/users/123?fields=id,name,email
   
   @GetMapping("/users/{id}")
   public Map<String, Object> getUser(
           @PathVariable String id,
           @RequestParam(required = false) Set<String> fields) {
       User user = userService.getUser(id);
       if (fields != null && !fields.isEmpty()) {
           return filterFields(user, fields);
       }
       return objectMapper.convertValue(user, Map.class);
   }

4. BATCH ENDPOINTS (reduce round trips):
   POST /api/users/batch
   Body: {"ids": ["1", "2", "3", "4", "5"]}
   Response: [user1, user2, user3, user4, user5]
   
   // Replaces 5 individual GET requests with 1 batch request

5. ASYNC/STREAMING FOR LARGE RESULTS:
   @GetMapping(value = "/reports/export", produces = MediaType.APPLICATION_NDJSON_VALUE)
   public Flux<ReportRow> exportReport(@RequestParam String reportId) {
       return reportService.streamReport(reportId);
       // Streams results one by one - client processes incrementally
       // No memory accumulation on server
   }

6. CONNECTION KEEP-ALIVE + HTTP/2:
   server:
     http2:
       enabled: true  # Multiplexing, header compression
   
   // Client side (WebClient)
   HttpClient httpClient = HttpClient.create()
       .protocol(HttpProtocol.H2);
```

### Q7: How do you design APIs for mobile/low-bandwidth clients?

```
MOBILE-OPTIMIZED API PATTERNS:

1. BFF (Backend for Frontend):
   ┌──────────┐        ┌──────────────┐
   │ Mobile   │──────→ │ Mobile BFF    │──→ Multiple internal APIs
   │ App      │        │ (aggregator)  │
   └──────────┘        └──────────────┘
   
   ┌──────────┐        ┌──────────────┐
   │ Web App  │──────→ │ Web BFF      │──→ Multiple internal APIs
   │          │        │ (aggregator)  │
   └──────────┘        └──────────────┘
   
   BFF aggregates, transforms, and optimizes for each client type
   Mobile BFF: smaller payloads, fewer calls
   Web BFF: richer data, more fields

2. GRAPHQL (client-driven queries):
   // Client requests exactly what it needs
   query {
     user(id: "123") {
       name
       avatar(size: THUMBNAIL)  # Mobile only needs thumbnail
       recentOrders(limit: 3) {
         id
         status
       }
     }
   }
   
   Spring Boot + GraphQL:
   @Controller
   public class UserGraphQLController {
       @QueryMapping
       public User user(@Argument String id) {
           return userService.getUser(id);
       }
       
       @SchemaMapping(typeName = "User")
       public List<Order> recentOrders(User user, @Argument int limit) {
           return orderService.getRecentOrders(user.getId(), limit);
       }
   }

3. DELTA SYNC (send only changes):
   GET /api/users?since=2024-03-14T10:00:00Z
   Response: Only users modified after that timestamp
   
   // Reduces bandwidth for sync-heavy mobile apps
   @GetMapping("/users")
   public SyncResponse<User> syncUsers(
           @RequestParam @DateTimeFormat(iso = ISO.DATE_TIME) Instant since) {
       List<User> modified = userRepo.findModifiedAfter(since);
       List<String> deleted = deletionLog.getDeletedAfter("users", since);
       return new SyncResponse<>(modified, deleted, Instant.now());
   }
```

---

## Problem 5: API Security at Scale

### Q8: How do you implement zero-trust API security?

```
ZERO-TRUST API SECURITY MODEL:

Principle: Never trust, always verify. Every request authenticated and authorized.

┌─────────────────────────────────────────────────────────────────┐
│  SECURITY LAYERS                                                 │
│                                                                   │
│  1. EDGE (API Gateway):                                          │
│     - TLS termination                                            │
│     - DDoS protection (rate limiting, WAF)                       │
│     - JWT validation (signature, expiry)                         │
│     - Basic authorization (audience check)                       │
│                                                                   │
│  2. SERVICE (Spring Security):                                   │
│     - Token validation (claims, scope)                           │
│     - Fine-grained authorization (@PreAuthorize)                 │
│     - Input validation                                           │
│     - Output filtering (field-level security)                    │
│                                                                   │
│  3. SERVICE-TO-SERVICE (mTLS):                                   │
│     - Mutual TLS for internal communication                      │
│     - Service identity via certificates                          │
│     - No network-level trust                                     │
│                                                                   │
│  4. DATA (Row-level security):                                   │
│     - Tenant isolation at DB level                               │
│     - Column-level encryption for PII                            │
│     - Audit trail for all data access                            │
└─────────────────────────────────────────────────────────────────┘

Spring Boot Implementation:

@Configuration
@EnableMethodSecurity
public class SecurityConfig {
    
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt
                    .decoder(jwtDecoder())
                    .jwtAuthenticationConverter(jwtAuthConverter())
                ))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/public/**").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .requestMatchers("/api/**").authenticated()
            )
            .sessionManagement(session -> session.sessionCreationPolicy(STATELESS));
        return http.build();
    }
}

// Fine-grained authorization
@RestController
public class OrderController {
    
    @GetMapping("/api/orders/{id}")
    @PreAuthorize("@orderAuthz.canRead(authentication, #id)")
    public Order getOrder(@PathVariable String id) {
        return orderService.getOrder(id);
    }
    
    @DeleteMapping("/api/orders/{id}")
    @PreAuthorize("hasRole('ADMIN') or @orderAuthz.isOwner(authentication, #id)")
    public void deleteOrder(@PathVariable String id) {
        orderService.deleteOrder(id);
    }
}

@Component("orderAuthz")
public class OrderAuthorizationService {
    public boolean canRead(Authentication auth, String orderId) {
        Order order = orderRepo.findById(orderId).orElse(null);
        if (order == null) return false;
        
        String userId = auth.getName();
        String tenantId = ((JwtAuthenticationToken) auth).getToken().getClaimAsString("tenant_id");
        
        // Must be same tenant AND (owner OR admin OR support role)
        return order.getTenantId().equals(tenantId) &&
            (order.getUserId().equals(userId) || hasRole(auth, "ADMIN", "SUPPORT"));
    }
}

// Service-to-service authentication (OAuth2 client credentials)
@Service
public class InternalApiClient {
    private final WebClient webClient;
    
    public InternalApiClient(
            @Qualifier("internal") OAuth2AuthorizedClientManager clientManager) {
        this.webClient = WebClient.builder()
            .filter(new ServerOAuth2AuthorizedClientExchangeFilterFunction(clientManager))
            .build();
    }
    
    public Mono<User> getUser(String userId) {
        return webClient.get()
            .uri("https://user-service/api/internal/users/{id}", userId)
            .attributes(clientRegistrationId("user-service"))
            .retrieve()
            .bodyToMono(User.class);
    }
}
```

---

## Problem 6: API Documentation and Developer Experience

### Q9: How do you keep API docs always up-to-date?

```
DOCUMENTATION STRATEGY: "Docs as Code"

Principle: Documentation generated FROM code, not maintained separately.

1. OpenAPI FROM CODE (Spring Boot generates spec):
   // springdoc-openapi library
   @Operation(summary = "Get user by ID",
              description = "Returns full user profile with recent activity")
   @ApiResponses({
       @ApiResponse(responseCode = "200", description = "User found",
           content = @Content(schema = @Schema(implementation = UserResponse.class))),
       @ApiResponse(responseCode = "404", description = "User not found",
           content = @Content(schema = @Schema(implementation = ProblemDetail.class)))
   })
   @GetMapping("/users/{id}")
   public UserResponse getUser(
       @Parameter(description = "User ID", example = "usr_123abc")
       @PathVariable String id) {
       return userService.getUser(id);
   }
   
   // Generated OpenAPI spec at: /v3/api-docs
   // Swagger UI at: /swagger-ui.html

2. CONTRACT-FIRST (spec drives code):
   // Write OpenAPI spec first → generate server stubs
   // Ensures spec and implementation never diverge
   
   // openapi-generator-maven-plugin
   <plugin>
       <groupId>org.openapitools</groupId>
       <artifactId>openapi-generator-maven-plugin</artifactId>
       <configuration>
           <inputSpec>${project.basedir}/src/main/resources/api-spec.yaml</inputSpec>
           <generatorName>spring</generatorName>
           <configOptions>
               <interfaceOnly>true</interfaceOnly>
               <useSpringBoot3>true</useSpringBoot3>
           </configOptions>
       </configuration>
   </plugin>

3. API PORTAL (centralized documentation):
   - Aggregate all service specs into one portal
   - Auto-update on deployment
   - Interactive "Try it out" with sandbox environment
   - SDK generation (TypeScript, Python, Go clients)
   - Changelog generation from spec diffs
   
   CI Pipeline:
     Build → Generate OpenAPI spec → Publish to API Portal
     → Generate client SDKs → Publish to package registry
     → Notify subscribers of changes

4. LIVING DOCUMENTATION (tests as docs):
   // Spring REST Docs generates docs FROM tests
   @Test
   void shouldReturnUser() {
       webTestClient.get().uri("/api/users/123")
           .exchange()
           .expectStatus().isOk()
           .expectBody()
           .consumeWith(document("get-user",
               pathParameters(
                   parameterWithName("id").description("The user's unique ID")),
               responseFields(
                   fieldWithPath("id").description("Unique identifier"),
                   fieldWithPath("name").description("Display name"),
                   fieldWithPath("email").description("Email address"))));
   }
   // Docs are always accurate because they're generated from passing tests
```
