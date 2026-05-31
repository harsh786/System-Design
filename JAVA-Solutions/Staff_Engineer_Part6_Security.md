# Staff Engineer - Part 6: Java Security Deep Dive
# JWT, OAuth2, OWASP Top 10, Cryptography, Spring Security Internals

---

## Q250: How does JWT (JSON Web Token) work internally?

**Structure:** `header.payload.signature` (Base64URL encoded)

```
eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyMSIsImV4cCI6MTcwMH0.signature
```

**Three Parts:**
```json
// Header
{"alg": "RS256", "typ": "JWT", "kid": "key-id-1"}

// Payload (Claims)
{"sub": "user123", "iat": 1700000000, "exp": 1700003600, 
 "roles": ["ADMIN"], "iss": "auth-service"}

// Signature
RSASHA256(base64UrlEncode(header) + "." + base64UrlEncode(payload), privateKey)
```

**Java Implementation:**
```java
// Creating JWT (using nimbus-jose-jwt or jjwt)
class JwtService {
    private final RSAPrivateKey privateKey;
    private final RSAPublicKey publicKey;
    
    // Sign JWT
    String createToken(String userId, Set<String> roles, Duration expiry) {
        Instant now = Instant.now();
        
        return Jwts.builder()
            .setHeaderParam("kid", "key-rotation-2024-01")
            .setSubject(userId)
            .setIssuedAt(Date.from(now))
            .setExpiration(Date.from(now.plus(expiry)))
            .claim("roles", roles)
            .claim("iss", "my-auth-service")
            .signWith(privateKey, SignatureAlgorithm.RS256)
            .compact();
    }
    
    // Verify JWT
    Claims verifyToken(String token) {
        try {
            return Jwts.parserBuilder()
                .setSigningKey(publicKey)
                .requireIssuer("my-auth-service")
                .setAllowedClockSkewSeconds(30)  // Handle clock drift
                .build()
                .parseClaimsJws(token)
                .getBody();
        } catch (ExpiredJwtException e) {
            throw new AuthException("Token expired");
        } catch (SignatureException e) {
            throw new AuthException("Invalid signature - token tampered");
        }
    }
}
```

**Critical Security Rules:**
1. **NEVER use `alg: none`** - attacker can strip signature
2. **NEVER use symmetric key (HS256) where public key expected** - algorithm confusion attack
3. **Always validate `iss`, `aud`, `exp`**
4. **Use RS256 (asymmetric) for distributed systems** - only auth service has private key
5. **Short expiry (15 min) + refresh tokens**
6. **Key rotation** - use `kid` header to identify which key signed it

---

## Q251: JWT vs Session-Based Authentication - When to use what?

| Aspect | JWT | Session |
|--------|-----|---------|
| Storage | Client (cookie/localStorage) | Server (Redis/DB) |
| Scalability | Stateless, no shared state | Need shared session store |
| Revocation | Hard (need blocklist) | Easy (delete from store) |
| Size | Large (payload in every request) | Small (just session ID) |
| Security | XSS risk if in localStorage | CSRF risk if in cookie |
| Best for | Microservices, APIs | Monoliths, web apps |

**Hybrid approach (production best practice):**
```java
// Short-lived JWT (15 min) + long-lived refresh token (7 days) in HttpOnly cookie
class TokenPair {
    String accessToken;   // JWT, 15 min, in Authorization header
    String refreshToken;  // Opaque, 7 days, HttpOnly Secure cookie, stored in DB
}

// Refresh flow:
// 1. Access token expires → 401
// 2. Client sends refresh token → server validates against DB
// 3. Issue new access token + rotate refresh token (one-time use)
// 4. If refresh token reused → REVOKE ALL tokens for that user (theft detected!)
```

---

## Q252: Explain OAuth 2.0 Authorization Code Flow with PKCE

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│  Client  │     │   Auth Server │     │  Resource    │
│  (SPA)   │     │  (Keycloak)  │     │  Server      │
└────┬─────┘     └──────┬───────┘     └──────┬───────┘
     │                   │                     │
     │ 1. Generate code_verifier + code_challenge
     │    (PKCE: Proof Key for Code Exchange)
     │                   │                     │
     │ 2. /authorize?response_type=code        │
     │    &client_id=app&redirect_uri=...      │
     │    &code_challenge=SHA256(verifier)      │
     │    &scope=read write                    │
     │──────────────────>│                     │
     │                   │                     │
     │ 3. User logs in + consents              │
     │                   │                     │
     │ 4. Redirect: /callback?code=AUTH_CODE   │
     │<──────────────────│                     │
     │                   │                     │
     │ 5. POST /token                          │
     │    code=AUTH_CODE&code_verifier=VERIFIER │
     │──────────────────>│                     │
     │                   │                     │
     │ 6. Verify: SHA256(verifier)==challenge   │
     │    Return: {access_token, refresh_token} │
     │<──────────────────│                     │
     │                   │                     │
     │ 7. GET /api/data  Authorization: Bearer │
     │─────────────────────────────────────────>
     │                   │                     │
     │ 8. Validate JWT signature + claims      │
     │<─────────────────────────────────────────
```

**Java Spring Security OAuth2 Implementation:**
```java
@Configuration
@EnableWebSecurity
class SecurityConfig {
    
    @Bean
    SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        return http
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/public/**").permitAll()
                .requestMatchers("/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt
                    .decoder(jwtDecoder())
                    .jwtAuthenticationConverter(jwtAuthConverter())
                )
            )
            .sessionManagement(session -> 
                session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .csrf(csrf -> csrf.disable())  // Stateless = no CSRF needed
            .build();
    }
    
    @Bean
    JwtDecoder jwtDecoder() {
        // Fetches JWKS (public keys) from auth server
        return NimbusJwtDecoder.withJwkSetUri(
            "https://auth.example.com/.well-known/jwks.json")
            .build();
    }
    
    @Bean
    JwtAuthenticationConverter jwtAuthConverter() {
        JwtGrantedAuthoritiesConverter authorities = new JwtGrantedAuthoritiesConverter();
        authorities.setAuthoritiesClaimName("roles");
        authorities.setAuthorityPrefix("ROLE_");
        
        JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
        converter.setJwtGrantedAuthoritiesConverter(authorities);
        return converter;
    }
}
```

---

## Q253: OWASP Top 10 - Java-Specific Mitigations

### 1. Injection (SQL, NoSQL, LDAP, OS Command)

```java
// VULNERABLE - SQL Injection
String query = "SELECT * FROM users WHERE name = '" + userInput + "'";
// Attack: userInput = "'; DROP TABLE users; --"

// SECURE - Parameterized Query
PreparedStatement ps = conn.prepareStatement("SELECT * FROM users WHERE name = ?");
ps.setString(1, userInput);  // Input is NEVER interpreted as SQL

// SECURE - JPA/Hibernate (always parameterized)
@Query("SELECT u FROM User u WHERE u.email = :email")
User findByEmail(@Param("email") String email);

// VULNERABLE - JPQL concatenation (yes, this is still injectable!)
String jpql = "SELECT u FROM User u WHERE u.name = '" + input + "'";
// SECURE
TypedQuery<User> q = em.createQuery("SELECT u FROM User u WHERE u.name = :n", User.class);
q.setParameter("n", input);
```

### 2. Broken Authentication

```java
// Password hashing - NEVER use MD5/SHA1/SHA256 alone!
// Use: BCrypt (default), SCrypt, Argon2id (best)

@Bean
PasswordEncoder passwordEncoder() {
    // Argon2id - memory-hard, GPU-resistant
    return new Argon2PasswordEncoder(16, 32, 1, 65536, 3);
    // saltLength=16, hashLength=32, parallelism=1, memory=64MB, iterations=3
}

// BCrypt (most common, still good)
@Bean
PasswordEncoder bcrypt() {
    return new BCryptPasswordEncoder(12);  // 2^12 rounds, ~250ms
}

// Timing-safe comparison (prevent timing attacks)
boolean verify(String provided, String stored) {
    return passwordEncoder.matches(provided, stored);
    // Internally uses MessageDigest.isEqual() - constant time
}
```

### 3. Sensitive Data Exposure

```java
// Encrypt sensitive data at rest
class EncryptionService {
    private static final String ALGORITHM = "AES/GCM/NoPadding";
    private final SecretKey key;  // From AWS KMS / HashiCorp Vault
    
    byte[] encrypt(byte[] plaintext) throws Exception {
        Cipher cipher = Cipher.getInstance(ALGORITHM);
        byte[] iv = new byte[12];  // 96-bit IV for GCM
        SecureRandom.getInstanceStrong().nextBytes(iv);
        
        cipher.init(Cipher.ENCRYPT_MODE, key, new GCMParameterSpec(128, iv));
        byte[] ciphertext = cipher.doFinal(plaintext);
        
        // Prepend IV to ciphertext (IV is not secret)
        return ByteBuffer.allocate(iv.length + ciphertext.length)
            .put(iv).put(ciphertext).array();
    }
    
    byte[] decrypt(byte[] data) throws Exception {
        ByteBuffer buffer = ByteBuffer.wrap(data);
        byte[] iv = new byte[12];
        buffer.get(iv);
        byte[] ciphertext = new byte[buffer.remaining()];
        buffer.get(ciphertext);
        
        Cipher cipher = Cipher.getInstance(ALGORITHM);
        cipher.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(128, iv));
        return cipher.doFinal(ciphertext);
    }
}

// TLS Configuration (disable weak protocols)
@Bean
TomcatServletWebServerFactory servletContainer() {
    TomcatServletWebServerFactory factory = new TomcatServletWebServerFactory();
    factory.addConnectorCustomizers(connector -> {
        connector.setProperty("sslEnabledProtocols", "TLSv1.2,TLSv1.3");
        connector.setProperty("ciphers", 
            "TLS_AES_256_GCM_SHA384,TLS_AES_128_GCM_SHA256");
    });
    return factory;
}
```

### 4. XML External Entity (XXE)

```java
// VULNERABLE - default XML parser allows external entities
DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
// Attack payload: <!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>

// SECURE - disable external entities
DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
factory.setXIncludeAware(false);
factory.setExpandEntityReferences(false);

// Or use JAXB/Jackson XML (safe by default)
```

### 5. Broken Access Control

```java
// VULNERABLE - IDOR (Insecure Direct Object Reference)
@GetMapping("/api/orders/{orderId}")
Order getOrder(@PathVariable Long orderId) {
    return orderRepo.findById(orderId).orElseThrow();  // Any user can access any order!
}

// SECURE - Always check ownership
@GetMapping("/api/orders/{orderId}")
Order getOrder(@PathVariable Long orderId, @AuthenticationPrincipal User user) {
    Order order = orderRepo.findById(orderId).orElseThrow();
    if (!order.getUserId().equals(user.getId())) {
        throw new AccessDeniedException("Not your order");
    }
    return order;
}

// BETTER - Query scoped to user
@GetMapping("/api/orders/{orderId}")
Order getOrder(@PathVariable Long orderId, @AuthenticationPrincipal User user) {
    return orderRepo.findByIdAndUserId(orderId, user.getId())
        .orElseThrow(() -> new NotFoundException("Order not found"));
    // Returns 404 whether it doesn't exist OR belongs to someone else (no info leak)
}
```

### 6. Security Misconfiguration

```java
// Production security checklist:
@Profile("production")
@Configuration
class ProductionSecurityConfig {
    
    @Bean
    SecurityFilterChain productionSecurity(HttpSecurity http) throws Exception {
        return http
            // Security headers
            .headers(h -> h
                .contentSecurityPolicy(csp -> 
                    csp.policyDirectives("default-src 'self'; script-src 'self'"))
                .httpStrictTransportSecurity(hsts -> 
                    hsts.maxAgeInSeconds(31536000).includeSubDomains(true))
                .frameOptions(fo -> fo.deny())
                .contentTypeOptions(Customizer.withDefaults())  // X-Content-Type-Options: nosniff
            )
            // CORS
            .cors(cors -> cors.configurationSource(corsConfig()))
            .build();
    }
    
    @Bean
    CorsConfigurationSource corsConfig() {
        CorsConfiguration config = new CorsConfiguration();
        config.setAllowedOrigins(List.of("https://myapp.com"));  // NOT "*" !
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE"));
        config.setAllowedHeaders(List.of("Authorization", "Content-Type"));
        config.setAllowCredentials(true);
        
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/api/**", config);
        return source;
    }
}
```

### 7. Cross-Site Scripting (XSS)

```java
// VULNERABLE - reflecting user input
@GetMapping("/search")
String search(@RequestParam String q, Model model) {
    model.addAttribute("query", q);  // <script>alert('xss')</script>
    return "search";  // Thymeleaf auto-escapes by default!
}

// Thymeleaf (safe by default):
// <p th:text="${query}">  → auto-escaped
// <p th:utext="${query}"> → UNSAFE! Raw HTML

// Manual sanitization for rich text:
class XssSanitizer {
    // Use OWASP Java HTML Sanitizer
    private static final PolicyFactory POLICY = new HtmlPolicyBuilder()
        .allowElements("p", "b", "i", "u", "a", "ul", "li")
        .allowUrlProtocols("https")
        .allowAttributes("href").onElements("a")
        .toFactory();
    
    String sanitize(String untrustedHtml) {
        return POLICY.sanitize(untrustedHtml);
    }
}

// Input validation (whitelist approach)
class InputValidator {
    private static final Pattern SAFE_STRING = Pattern.compile("^[a-zA-Z0-9\\s\\-_.@]+$");
    
    String validateInput(String input, int maxLength) {
        if (input == null || input.length() > maxLength) {
            throw new ValidationException("Invalid input length");
        }
        if (!SAFE_STRING.matcher(input).matches()) {
            throw new ValidationException("Invalid characters");
        }
        return input;
    }
}
```

### 8. Insecure Deserialization

```java
// VULNERABLE - Java native deserialization (NEVER deserialize untrusted data!)
ObjectInputStream ois = new ObjectInputStream(untrustedInput);
Object obj = ois.readObject();  // Remote Code Execution!

// Attacks: Apache Commons Collections gadget chains, etc.

// MITIGATIONS:
// 1. NEVER use Java serialization for external data
// 2. Use JSON (Jackson) with strict typing
// 3. If you MUST use Java serialization:
ObjectInputFilter filter = ObjectInputFilter.Config.createFilter(
    "com.myapp.model.*;!*"  // Only allow your classes
);
ois.setObjectInputFilter(filter);

// Jackson - prevent polymorphic deserialization attacks
ObjectMapper mapper = new ObjectMapper();
mapper.activateDefaultTyping(
    mapper.getPolymorphicTypeValidator(),
    ObjectMapper.DefaultTyping.NON_FINAL,
    JsonTypeInfo.As.PROPERTY
);
// Better: Don't use @JsonTypeInfo on untrusted input at all!

// Safest: Use records/DTOs with explicit fields
record CreateUserRequest(
    @NotBlank String name,
    @Email String email,
    @Size(min = 8, max = 100) String password
) {}
```

### 9. Using Components with Known Vulnerabilities

```java
// Tools to detect:
// 1. OWASP Dependency-Check (Maven/Gradle plugin)
// 2. Snyk
// 3. GitHub Dependabot

// Maven:
// <plugin>
//   <groupId>org.owasp</groupId>
//   <artifactId>dependency-check-maven</artifactId>
//   <configuration>
//     <failBuildOnCVSS>7</failBuildOnCVSS>  <!-- Fail on HIGH severity -->
//   </configuration>
// </plugin>

// Gradle:
// plugins { id 'org.owasp.dependencycheck' version '9.0.0' }
// dependencyCheck { failBuildOnCVSS = 7.0f }
```

### 10. Insufficient Logging & Monitoring

```java
// Security event logging
@Component
class SecurityAuditLogger {
    private static final Logger audit = LoggerFactory.getLogger("SECURITY_AUDIT");
    
    void logAuthSuccess(String userId, String ip) {
        audit.info("AUTH_SUCCESS user={} ip={} timestamp={}", 
            userId, ip, Instant.now());
    }
    
    void logAuthFailure(String attemptedUser, String ip, String reason) {
        audit.warn("AUTH_FAILURE user={} ip={} reason={} timestamp={}",
            attemptedUser, ip, reason, Instant.now());
        
        // Brute force detection
        if (failureCounter.incrementAndGet(ip) > 5) {
            audit.error("BRUTE_FORCE_DETECTED ip={} attempts={}", ip, 
                failureCounter.get(ip));
            // Block IP temporarily
        }
    }
    
    void logAccessDenied(String userId, String resource, String action) {
        audit.warn("ACCESS_DENIED user={} resource={} action={}", 
            userId, resource, action);
    }
    
    void logSensitiveDataAccess(String userId, String dataType, String recordId) {
        audit.info("SENSITIVE_ACCESS user={} type={} record={}", 
            userId, dataType, recordId);
    }
}
```

---

## Q254: Spring Security Filter Chain - How does it work internally?

```
HTTP Request
     │
     ▼
┌─────────────────────────────────────────────────┐
│            DelegatingFilterProxy                  │
│  (Servlet Filter → delegates to Spring bean)     │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│         FilterChainProxy                         │
│  (Matches request to correct SecurityFilterChain)│
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  SecurityFilterChain (ordered filters):          │
│                                                  │
│  1. SecurityContextPersistenceFilter             │
│     → Load SecurityContext from session/token    │
│                                                  │
│  2. CorsFilter                                   │
│     → Handle CORS preflight                      │
│                                                  │
│  3. CsrfFilter                                   │
│     → Validate CSRF token                        │
│                                                  │
│  4. LogoutFilter                                 │
│     → Handle /logout                             │
│                                                  │
│  5. UsernamePasswordAuthenticationFilter         │
│     → Handle form login POST /login             │
│                                                  │
│  6. BearerTokenAuthenticationFilter              │
│     → Extract and validate JWT                   │
│                                                  │
│  7. ExceptionTranslationFilter                   │
│     → Convert security exceptions to responses   │
│                                                  │
│  8. FilterSecurityInterceptor                    │
│     → Final authorization check                  │
│                                                  │
└─────────────────────────────────────────────────┘
```

```java
// Custom security filter (e.g., API key authentication)
class ApiKeyAuthFilter extends OncePerRequestFilter {
    
    @Override
    protected void doFilterInternal(HttpServletRequest request, 
            HttpServletResponse response, FilterChain chain) 
            throws ServletException, IOException {
        
        String apiKey = request.getHeader("X-API-Key");
        
        if (apiKey != null) {
            // Validate API key (constant-time comparison!)
            Optional<ApiClient> client = apiKeyService.validate(apiKey);
            
            if (client.isPresent()) {
                // Set authentication in SecurityContext
                ApiKeyAuthentication auth = new ApiKeyAuthentication(
                    client.get(), client.get().getAuthorities());
                SecurityContextHolder.getContext().setAuthentication(auth);
            }
        }
        
        chain.doFilter(request, response);  // Continue chain
    }
}

// Register custom filter
@Bean
SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
    return http
        .addFilterBefore(new ApiKeyAuthFilter(), 
            UsernamePasswordAuthenticationFilter.class)
        .build();
}
```

---

## Q255: Cryptography in Java - What to use and what to avoid?

| Use Case | Correct Algorithm | NEVER Use |
|----------|------------------|-----------|
| Password hashing | Argon2id, BCrypt, SCrypt | MD5, SHA-256 (alone) |
| Symmetric encryption | AES-256-GCM | DES, 3DES, AES-ECB |
| Asymmetric encryption | RSA-OAEP (2048+ bit) | RSA PKCS#1 v1.5 |
| Digital signatures | Ed25519, RSA-PSS, ECDSA | RSA PKCS#1 v1.5 |
| Key exchange | X25519, ECDH | Static DH |
| Hashing (non-password) | SHA-256, SHA-3, BLAKE3 | MD5, SHA-1 |
| Random numbers | SecureRandom | Random, Math.random() |
| MAC | HMAC-SHA256 | Custom MAC |

```java
// Secure random number generation
SecureRandom random = SecureRandom.getInstanceStrong();
byte[] token = new byte[32];
random.nextBytes(token);
String apiKey = Base64.getUrlEncoder().withoutPadding().encodeToString(token);

// HMAC for API request signing
class HmacSigner {
    Mac createHmac(byte[] secret) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(secret, "HmacSHA256"));
        return mac;
    }
    
    String sign(String payload, byte[] secret) throws Exception {
        Mac mac = createHmac(secret);
        byte[] signature = mac.doFinal(payload.getBytes(StandardCharsets.UTF_8));
        return Base64.getUrlEncoder().withoutPadding().encodeToString(signature);
    }
    
    boolean verify(String payload, String signature, byte[] secret) throws Exception {
        String expected = sign(payload, secret);
        // Constant-time comparison to prevent timing attacks!
        return MessageDigest.isEqual(
            expected.getBytes(StandardCharsets.UTF_8),
            signature.getBytes(StandardCharsets.UTF_8));
    }
}

// Key derivation (e.g., from password to encryption key)
class KeyDerivation {
    SecretKey deriveKey(String password, byte[] salt) throws Exception {
        SecretKeyFactory factory = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256");
        KeySpec spec = new PBEKeySpec(password.toCharArray(), salt, 600_000, 256);
        byte[] keyBytes = factory.generateSecret(spec).getEncoded();
        return new SecretKeySpec(keyBytes, "AES");
    }
}
```

---

## Q256: How to implement Role-Based + Attribute-Based Access Control (RBAC + ABAC)?

```java
// RBAC: Simple role check
@PreAuthorize("hasRole('ADMIN')")
@DeleteMapping("/users/{id}")
void deleteUser(@PathVariable Long id) { ... }

// ABAC: Complex attribute-based rules
@PreAuthorize("@accessControl.canAccess(#id, authentication)")
@GetMapping("/documents/{id}")
Document getDocument(@PathVariable Long id) { ... }

@Component("accessControl")
class AccessControlService {
    
    boolean canAccess(Long documentId, Authentication auth) {
        Document doc = documentRepo.findById(documentId).orElse(null);
        if (doc == null) return false;
        
        User user = (User) auth.getPrincipal();
        
        // Rule 1: Owner can always access
        if (doc.getOwnerId().equals(user.getId())) return true;
        
        // Rule 2: Same department can access if document is INTERNAL
        if (doc.getVisibility() == Visibility.INTERNAL 
            && doc.getDepartment().equals(user.getDepartment())) return true;
        
        // Rule 3: Admin can access everything
        if (auth.getAuthorities().stream()
            .anyMatch(a -> a.getAuthority().equals("ROLE_ADMIN"))) return true;
        
        // Rule 4: Time-based access (e.g., during business hours only)
        if (doc.getAccessPolicy() == AccessPolicy.BUSINESS_HOURS) {
            LocalTime now = LocalTime.now();
            return now.isAfter(LocalTime.of(9, 0)) && now.isBefore(LocalTime.of(17, 0));
        }
        
        return false;
    }
}

// Method security with custom annotation
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
@PreAuthorize("@tenantSecurity.belongsToTenant(#tenantId, authentication)")
@interface RequireTenantAccess {
    String tenantIdParam() default "tenantId";
}

@RequireTenantAccess
@GetMapping("/tenants/{tenantId}/data")
List<Data> getTenantData(@PathVariable String tenantId) { ... }
```

---

## Q257: How to handle secrets management in Java applications?

```java
// NEVER: hardcode secrets
// NEVER: store in application.properties in git
// NEVER: pass as command line arguments (visible in ps)

// OPTION 1: Environment variables (12-factor app)
@Value("${DB_PASSWORD}")
private String dbPassword;

// OPTION 2: Spring Cloud Vault (HashiCorp Vault)
// application.yml:
// spring:
//   cloud:
//     vault:
//       uri: https://vault.example.com
//       authentication: KUBERNETES
//       kubernetes:
//         role: my-app
//       kv:
//         backend: secret
//         default-context: my-app

@Value("${database.password}")  // Auto-fetched from Vault
private String dbPassword;

// OPTION 3: AWS Secrets Manager
@Configuration
class SecretsConfig {
    
    @Bean
    DataSource dataSource(SecretsManagerClient client) {
        GetSecretValueResponse secret = client.getSecretValue(
            GetSecretValueRequest.builder()
                .secretId("prod/myapp/database")
                .build());
        
        JsonNode creds = objectMapper.readTree(secret.secretString());
        
        return DataSourceBuilder.create()
            .url(creds.get("url").asText())
            .username(creds.get("username").asText())
            .password(creds.get("password").asText())
            .build();
    }
}

// OPTION 4: Sealed Secrets / SOPS for Kubernetes
// Encrypted in git, decrypted at deploy time

// Secret rotation without downtime:
class RotatingSecretDataSource {
    private volatile DataSource current;
    
    @Scheduled(fixedRate = 3600000)  // Check every hour
    void refreshCredentials() {
        String newPassword = secretsManager.getLatestPassword();
        DataSource newDs = createDataSource(newPassword);
        
        // Verify new connection works
        try (Connection conn = newDs.getConnection()) {
            conn.isValid(5);
            DataSource old = current;
            current = newDs;
            // Gracefully close old (after in-flight queries complete)
            scheduledClose(old, Duration.ofMinutes(5));
        }
    }
}
```

---

## Q258: Rate Limiting + Brute Force Protection in Spring Security

```java
@Component
class BruteForceProtectionFilter extends OncePerRequestFilter {
    
    // Sliding window per IP (Caffeine cache with TTL)
    private final Cache<String, AtomicInteger> attempts = Caffeine.newBuilder()
        .expireAfterWrite(Duration.ofMinutes(15))
        .build();
    
    private static final int MAX_ATTEMPTS = 5;
    
    @Override
    protected void doFilterInternal(HttpServletRequest request,
            HttpServletResponse response, FilterChain chain) 
            throws ServletException, IOException {
        
        String ip = getClientIp(request);
        
        if (isBlocked(ip)) {
            response.setStatus(429);
            response.getWriter().write(
                """{"error": "Too many attempts. Try again in 15 minutes."}""");
            return;
        }
        
        chain.doFilter(request, response);
    }
    
    void recordFailedAttempt(String ip) {
        attempts.get(ip, k -> new AtomicInteger(0)).incrementAndGet();
    }
    
    boolean isBlocked(String ip) {
        AtomicInteger count = attempts.getIfPresent(ip);
        return count != null && count.get() >= MAX_ATTEMPTS;
    }
    
    void resetAttempts(String ip) {
        attempts.invalidate(ip);
    }
    
    private String getClientIp(HttpServletRequest request) {
        String xff = request.getHeader("X-Forwarded-For");
        if (xff != null && !xff.isEmpty()) {
            return xff.split(",")[0].trim();  // First IP in chain
        }
        return request.getRemoteAddr();
    }
}

// Account lockout (DB-based, survives restarts)
@Service
class AccountLockoutService {
    
    @Transactional
    void handleFailedLogin(String username) {
        User user = userRepo.findByUsername(username);
        if (user == null) return;  // Don't reveal if user exists!
        
        user.setFailedAttempts(user.getFailedAttempts() + 1);
        
        if (user.getFailedAttempts() >= 5) {
            user.setLockedUntil(Instant.now().plus(Duration.ofMinutes(30)));
            // Send alert email
        }
    }
    
    boolean isLocked(String username) {
        User user = userRepo.findByUsername(username);
        return user != null && user.getLockedUntil() != null 
            && user.getLockedUntil().isAfter(Instant.now());
    }
}
```

---

## Q259: How to implement Multi-Tenancy Security?

```java
// Approach: Row-Level Security via Hibernate Filter

@Entity
@FilterDef(name = "tenantFilter", parameters = @ParamDef(name = "tenantId", type = String.class))
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
class Order {
    @Id Long id;
    @Column(name = "tenant_id") String tenantId;
    // ... other fields
}

// Tenant context (ThreadLocal, propagated via MDC)
class TenantContext {
    private static final ThreadLocal<String> CURRENT_TENANT = new ThreadLocal<>();
    
    static void setTenant(String tenantId) { CURRENT_TENANT.set(tenantId); }
    static String getTenant() { return CURRENT_TENANT.get(); }
    static void clear() { CURRENT_TENANT.remove(); }
}

// Filter that extracts tenant from JWT
class TenantFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request,
            HttpServletResponse response, FilterChain chain) 
            throws ServletException, IOException {
        
        String tenantId = extractTenantFromJwt(request);
        TenantContext.setTenant(tenantId);
        
        // Enable Hibernate filter for this session
        Session session = entityManager.unwrap(Session.class);
        session.enableFilter("tenantFilter").setParameter("tenantId", tenantId);
        
        try {
            chain.doFilter(request, response);
        } finally {
            TenantContext.clear();
        }
    }
}

// Prevent cross-tenant data access in writes too:
@EntityListeners(TenantListener.class)
class BaseEntity {
    @Column(name = "tenant_id", updatable = false)
    String tenantId;
}

class TenantListener {
    @PrePersist
    void setTenant(BaseEntity entity) {
        entity.setTenantId(TenantContext.getTenant());
    }
    
    @PreUpdate @PreRemove
    void verifyTenant(BaseEntity entity) {
        if (!entity.getTenantId().equals(TenantContext.getTenant())) {
            throw new SecurityException("Cross-tenant access attempt!");
        }
    }
}
```

---

## Q260: Security Anti-Patterns in Java (What NOT to do)

```java
// 1. ANTI-PATTERN: Rolling your own crypto
String hash = md5(password + "salt");  // NO! Use BCrypt/Argon2

// 2. ANTI-PATTERN: Comparing secrets with .equals()
if (providedToken.equals(storedToken)) // NO! Timing attack
if (MessageDigest.isEqual(a, b))       // YES! Constant time

// 3. ANTI-PATTERN: Catching and swallowing security exceptions
try { authorize(user, resource); } 
catch (Exception e) { /* ignore */ }  // NO! Fail-closed!

// 4. ANTI-PATTERN: Trusting client-side validation
// Client says user.role = "ADMIN"? Verify server-side!

// 5. ANTI-PATTERN: Verbose error messages
// "Invalid password for user john@example.com" → reveals user exists!
// CORRECT: "Invalid username or password" (same message for both)

// 6. ANTI-PATTERN: Logging sensitive data
log.info("User login: email={}, password={}", email, password);  // NO!
log.info("User login: email={}", email);  // YES

// 7. ANTI-PATTERN: Using String for sensitive data
String password = request.getParameter("password");  
// String is immutable, stays in memory until GC!
// Better: use char[] and zero it after use
char[] password = ...;
try { authenticate(password); }
finally { Arrays.fill(password, '\0'); }

// 8. ANTI-PATTERN: Not validating redirect URLs
String redirect = request.getParameter("redirect");
response.sendRedirect(redirect);  // Open redirect attack!
// CORRECT:
if (isAllowedRedirect(redirect)) response.sendRedirect(redirect);

// 9. ANTI-PATTERN: Using HTTP for internal services
// "But it's internal!" → lateral movement after breach
// ALWAYS use mTLS between microservices

// 10. ANTI-PATTERN: Static API keys that never rotate
// Use short-lived tokens with automatic rotation
```

---

## Q261: Secure Microservices Communication Patterns

```java
// Pattern 1: mTLS (Mutual TLS) between services
// Both client and server present certificates

// Spring Boot mTLS config:
// server:
//   ssl:
//     enabled: true
//     key-store: classpath:server-keystore.p12
//     key-store-password: ${KEYSTORE_PASS}
//     trust-store: classpath:truststore.p12
//     trust-store-password: ${TRUST_PASS}
//     client-auth: need  # Require client certificate

// Pattern 2: Service Mesh (Istio/Linkerd handles mTLS transparently)
// No code changes! Sidecar proxy handles encryption

// Pattern 3: JWT propagation between services
@Component
class ServiceAuthInterceptor implements ClientHttpRequestInterceptor {
    private final JwtService jwtService;
    
    @Override
    public ClientHttpResponse intercept(HttpRequest request, byte[] body,
            ClientHttpRequestExecution execution) throws IOException {
        
        // Get current user's JWT and propagate it
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth instanceof JwtAuthenticationToken jwtAuth) {
            request.getHeaders().setBearerAuth(jwtAuth.getToken().getTokenValue());
        }
        
        return execution.execute(request, body);
    }
}

// Pattern 4: Service-to-Service tokens (no user context)
class ServiceTokenProvider {
    private volatile String cachedToken;
    private volatile Instant tokenExpiry;
    
    synchronized String getServiceToken() {
        if (cachedToken == null || Instant.now().isAfter(tokenExpiry.minus(Duration.ofMinutes(5)))) {
            // Client credentials grant (OAuth2)
            TokenResponse response = oauthClient.clientCredentials(
                "my-service", secret, "scope:read scope:write");
            cachedToken = response.getAccessToken();
            tokenExpiry = Instant.now().plus(Duration.ofSeconds(response.getExpiresIn()));
        }
        return cachedToken;
    }
}
```

---

## Q262: Content Security Policy (CSP) and Security Headers

```java
@Bean
SecurityFilterChain securityHeaders(HttpSecurity http) throws Exception {
    return http
        .headers(headers -> headers
            // Prevent clickjacking
            .frameOptions(frame -> frame.deny())
            
            // Prevent MIME sniffing
            .contentTypeOptions(Customizer.withDefaults())
            
            // XSS Protection (legacy browsers)
            .xssProtection(xss -> xss.headerValue(
                XXssProtectionHeaderWriter.HeaderValue.ENABLED_MODE_BLOCK))
            
            // HSTS (force HTTPS)
            .httpStrictTransportSecurity(hsts -> hsts
                .maxAgeInSeconds(31536000)
                .includeSubDomains(true)
                .preload(true))
            
            // CSP (prevent XSS, data injection)
            .contentSecurityPolicy(csp -> csp
                .policyDirectives(String.join("; ",
                    "default-src 'self'",
                    "script-src 'self' 'nonce-{random}'",
                    "style-src 'self' 'unsafe-inline'",
                    "img-src 'self' data: https:",
                    "font-src 'self'",
                    "connect-src 'self' https://api.example.com",
                    "frame-ancestors 'none'",
                    "base-uri 'self'",
                    "form-action 'self'"
                )))
            
            // Referrer Policy
            .referrerPolicy(ref -> ref
                .policy(ReferrerPolicyHeaderWriter.ReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN))
            
            // Permissions Policy
            .permissionsPolicy(pp -> pp
                .policy("camera=(), microphone=(), geolocation=()"))
        )
        .build();
}
```

---

## Q263: How to prevent Mass Assignment / Over-Posting attacks?

```java
// VULNERABLE: Binding all fields from request
@PostMapping("/users")
User createUser(@RequestBody User user) {  // Attacker sends: {"role": "ADMIN"} !
    return userRepo.save(user);
}

// SECURE: Use DTOs with only allowed fields
record CreateUserRequest(
    @NotBlank String name,
    @Email String email,
    @Size(min = 8) String password
    // No 'role' field! Cannot be set by user
) {}

@PostMapping("/users")
User createUser(@Valid @RequestBody CreateUserRequest request) {
    User user = new User();
    user.setName(request.name());
    user.setEmail(request.email());
    user.setPassword(encoder.encode(request.password()));
    user.setRole(Role.USER);  // Server sets role!
    return userRepo.save(user);
}

// ALSO: Use @JsonIgnoreProperties on entities
@Entity
@JsonIgnoreProperties({"role", "isAdmin", "createdAt"})
class User { ... }

// BEST: Never expose entities in API, always use DTOs
```

---

## Summary: Security Checklist for Staff Engineers

```
AUTHENTICATION:
□ Argon2id/BCrypt for passwords (NEVER MD5/SHA)
□ Short-lived JWT (15 min) + refresh tokens
□ Multi-factor authentication for sensitive operations
□ Account lockout + brute force protection
□ Session fixation protection

AUTHORIZATION:
□ RBAC + ABAC combination
□ Always check ownership (prevent IDOR)
□ DTOs to prevent mass assignment
□ Row-level security for multi-tenancy

TRANSPORT:
□ TLS 1.2+ only (no SSLv3, TLS 1.0/1.1)
□ mTLS between microservices
□ Certificate pinning for mobile apps

DATA:
□ AES-256-GCM for encryption at rest
□ Secrets in Vault/KMS (NEVER in code/git)
□ PII encryption + audit logging
□ GDPR: right to erasure, data minimization

HEADERS:
□ CSP, HSTS, X-Frame-Options, X-Content-Type-Options
□ CORS whitelist (never wildcard with credentials)
□ Referrer-Policy, Permissions-Policy

INPUT:
□ Parameterized queries (prevent SQLi)
□ HTML sanitization (prevent XSS)
□ File upload validation (type, size, virus scan)
□ Disable XML external entities (XXE)

DEPENDENCIES:
□ OWASP Dependency-Check in CI/CD
□ Automated vulnerability scanning
□ Regular dependency updates
□ SBOM (Software Bill of Materials)
```

