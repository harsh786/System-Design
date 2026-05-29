# Spring Security Internals - Staff Engineer Deep Dive

## 1. Spring Security Architecture

### 1.1 How Spring Security Integrates with Servlet Container

```
┌─────────────────────────────────────────────────────────────────┐
│                      Servlet Container (Tomcat)                   │
│                                                                   │
│  Request → [Servlet Filters] → DispatcherServlet → Controllers   │
│                    ↑                                              │
│         DelegatingFilterProxy                                     │
│                    ↓                                              │
│            FilterChainProxy                                       │
│                    ↓                                              │
│     [SecurityFilterChain 1, 2, ... N]                            │
└─────────────────────────────────────────────────────────────────┘
```

**DelegatingFilterProxy** is a standard Servlet Filter registered in `web.xml` or via `AbstractSecurityWebApplicationInitializer`. It bridges the Servlet container lifecycle with Spring's ApplicationContext:

```java
// DelegatingFilterProxy internals (simplified)
public class DelegatingFilterProxy extends GenericFilterBean {
    private String targetBeanName; // "springSecurityFilterChain"
    private volatile Filter delegate;
    
    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain) {
        Filter delegateToUse = this.delegate;
        if (delegateToUse == null) {
            WebApplicationContext wac = findWebApplicationContext();
            delegateToUse = wac.getBean(targetBeanName, Filter.class);
            this.delegate = delegateToUse;
        }
        delegateToUse.doFilter(req, res, chain);
    }
}
```

**FilterChainProxy** holds multiple SecurityFilterChain instances and delegates to the first matching chain:

```java
public class FilterChainProxy extends GenericFilterBean {
    private List<SecurityFilterChain> filterChains;
    
    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain) {
        // Find matching chain
        List<Filter> filters = getFilters((HttpServletRequest) req);
        if (filters == null || filters.isEmpty()) {
            chain.doFilter(req, res); // no security
            return;
        }
        VirtualFilterChain virtualChain = new VirtualFilterChain(chain, filters);
        virtualChain.doFilter(req, res);
    }
    
    private List<Filter> getFilters(HttpServletRequest request) {
        for (SecurityFilterChain chain : this.filterChains) {
            if (chain.matches(request)) {
                return chain.getFilters();
            }
        }
        return null;
    }
}
```

### 1.2 SecurityFilterChain - Complete Filter Ordering

Spring Security 6.x default filter chain ordering:

```
┌────────────────────────────────────────────────────────────────────┐
│ Filter Order (Spring Security 6.x)                                  │
├─────┬──────────────────────────────────────────────────────────────┤
│  1  │ ForceEagerSessionCreationFilter (if configured)              │
│  2  │ ChannelProcessingFilter (HTTP→HTTPS redirect)                │
│  3  │ WebAsyncManagerIntegrationFilter                             │
│  4  │ SecurityContextHolderFilter (replaces Persistence filter)    │
│  5  │ HeaderWriterFilter (security headers)                        │
│  6  │ CorsFilter                                                   │
│  7  │ CsrfFilter                                                   │
│  8  │ LogoutFilter                                                  │
│  9  │ OAuth2AuthorizationRequestRedirectFilter                     │
│ 10  │ Saml2WebSsoAuthenticationRequestFilter                       │
│ 11  │ X509AuthenticationFilter                                      │
│ 12  │ AbstractPreAuthenticatedProcessingFilter                     │
│ 13  │ UsernamePasswordAuthenticationFilter                         │
│ 14  │ OAuth2LoginAuthenticationFilter                              │
│ 15  │ DefaultLoginPageGeneratingFilter                             │
│ 16  │ DefaultLogoutPageGeneratingFilter                            │
│ 17  │ BearerTokenAuthenticationFilter                              │
│ 18  │ RequestCacheAwareFilter                                      │
│ 19  │ SecurityContextHolderAwareRequestFilter                      │
│ 20  │ AnonymousAuthenticationFilter                                │
│ 21  │ SessionManagementFilter                                      │
│ 22  │ ExceptionTranslationFilter                                   │
│ 23  │ AuthorizationFilter (replaces FilterSecurityInterceptor)     │
└─────┴──────────────────────────────────────────────────────────────┘
```

**Key filters explained:**

| Filter | Purpose |
|--------|---------|
| `SecurityContextHolderFilter` | Loads SecurityContext from repository, sets it on SecurityContextHolder. In Spring Security 6, context is NOT auto-saved (explicit save required) |
| `HeaderWriterFilter` | Writes X-Content-Type-Options, X-Frame-Options, HSTS, etc. |
| `CsrfFilter` | Validates CSRF token on state-changing requests |
| `LogoutFilter` | Matches logout URL, performs logout handlers (invalidate session, clear cookies) |
| `UsernamePasswordAuthenticationFilter` | Extracts username/password from POST /login, delegates to AuthenticationManager |
| `BearerTokenAuthenticationFilter` | Extracts Bearer token from Authorization header, validates via AuthenticationManager |
| `ExceptionTranslationFilter` | Catches AccessDeniedException and AuthenticationException, delegates to entry points |
| `AuthorizationFilter` | Evaluates authorization rules (replaces FilterSecurityInterceptor in Spring Security 6) |

### 1.3 SecurityContextPersistenceFilter vs SecurityContextHolderFilter

**Spring Security 5 (Deprecated):**
```java
// SecurityContextPersistenceFilter - auto-saves context after request
public class SecurityContextPersistenceFilter {
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain) {
        SecurityContext contextBeforeChain = repo.loadContext(holder);
        try {
            SecurityContextHolder.setContext(contextBeforeChain);
            chain.doFilter(req, res);
        } finally {
            SecurityContext contextAfterChain = SecurityContextHolder.getContext();
            SecurityContextHolder.clearContext();
            repo.saveContext(contextAfterChain, req, res); // AUTO-SAVE
        }
    }
}
```

**Spring Security 6 (Current):**
```java
// SecurityContextHolderFilter - requires EXPLICIT save
public class SecurityContextHolderFilter {
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain) {
        Supplier<SecurityContext> deferredContext = repo.loadDeferredContext(req);
        try {
            SecurityContextHolder.setDeferredContext(deferredContext); // LAZY loading
            chain.doFilter(req, res);
        } finally {
            SecurityContextHolder.clearContext();
            // NO auto-save - you must call SecurityContextRepository.saveContext()
        }
    }
}
```

**Why the change?** Prevents accidental context persistence, eliminates session creation side effects, better for stateless apps.

### 1.4 Authentication Flow

```
┌──────────┐     ┌───────────────────┐     ┌──────────────────────┐
│  Filter   │────→│AuthenticationManager│────→│AuthenticationProvider│
│(extracts  │     │   (ProviderManager)│     │  (DaoAuthProvider,   │
│ credentials)    │                    │     │   JwtAuthProvider)   │
└──────────┘     └───────────────────┘     └──────────┬───────────┘
                                                       │
                                           ┌───────────▼───────────┐
                                           │  UserDetailsService   │
                                           │  (loads user by name) │
                                           └───────────┬───────────┘
                                                       │
                                           ┌───────────▼───────────┐
                                           │  PasswordEncoder      │
                                           │  (BCrypt, Argon2)     │
                                           └───────────────────────┘
```

```java
// ProviderManager iterates through providers
public class ProviderManager implements AuthenticationManager {
    private List<AuthenticationProvider> providers;
    private AuthenticationManager parent; // fallback
    
    public Authentication authenticate(Authentication auth) throws AuthenticationException {
        for (AuthenticationProvider provider : providers) {
            if (!provider.supports(auth.getClass())) continue;
            
            try {
                Authentication result = provider.authenticate(auth);
                if (result != null) {
                    // Copy details, erase credentials
                    copyDetails(auth, result);
                    return result;
                }
            } catch (AuthenticationException e) {
                lastException = e;
            }
        }
        // Try parent if available
        if (parent != null) {
            return parent.authenticate(auth);
        }
        throw lastException;
    }
}
```

```java
// DaoAuthenticationProvider internals
public class DaoAuthenticationProvider extends AbstractUserDetailsAuthenticationProvider {
    private UserDetailsService userDetailsService;
    private PasswordEncoder passwordEncoder;
    
    @Override
    protected UserDetails retrieveUser(String username, 
            UsernamePasswordAuthenticationToken auth) {
        UserDetails user = userDetailsService.loadUserByUsername(username);
        if (user == null) throw new UsernameNotFoundException(username);
        return user;
    }
    
    @Override
    protected void additionalAuthenticationChecks(UserDetails userDetails,
            UsernamePasswordAuthenticationToken auth) {
        String presentedPassword = auth.getCredentials().toString();
        if (!passwordEncoder.matches(presentedPassword, userDetails.getPassword())) {
            throw new BadCredentialsException("Bad credentials");
        }
    }
}
```

### 1.5 SecurityContext Storage Strategies

```java
public class SecurityContextHolder {
    public static final String MODE_THREADLOCAL = "MODE_THREADLOCAL";
    public static final String MODE_INHERITABLETHREADLOCAL = "MODE_INHERITABLETHREADLOCAL";
    public static final String MODE_GLOBAL = "MODE_GLOBAL";
    
    // Default: ThreadLocal - context per thread, not inherited by child threads
    // InheritableThreadLocal - child threads inherit parent's context (careful with thread pools!)
    // Global - single context for entire JVM (testing only)
}
```

**ThreadLocal issue with async:**
```java
// Problem: @Async methods lose SecurityContext
@Async
public CompletableFuture<String> asyncMethod() {
    // SecurityContextHolder.getContext() is EMPTY here!
}

// Solution 1: DelegatingSecurityContextExecutor
@Bean
public Executor taskExecutor() {
    ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
    executor.setCorePoolSize(4);
    executor.initialize();
    return new DelegatingSecurityContextAsyncTaskExecutor(executor);
}

// Solution 2: SecurityContext propagation
@Bean
public Executor taskExecutor() {
    ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
    executor.setTaskDecorator(runnable -> {
        SecurityContext context = SecurityContextHolder.getContext();
        return () -> {
            try {
                SecurityContextHolder.setContext(context);
                runnable.run();
            } finally {
                SecurityContextHolder.clearContext();
            }
        };
    });
    return executor;
}
```

### 1.6 Authorization Flow (Spring Security 6)

Spring Security 6 replaces `AccessDecisionManager` with `AuthorizationManager`:

```java
// New in Spring Security 6
public interface AuthorizationManager<T> {
    AuthorizationDecision check(Supplier<Authentication> authentication, T object);
}

// AuthorizationFilter uses AuthorizationManager
public class AuthorizationFilter extends GenericFilterBean {
    private final AuthorizationManager<HttpServletRequest> authorizationManager;
    
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain) {
        AuthorizationDecision decision = authorizationManager.check(
            SecurityContextHolder::getContext().getAuthentication(),
            (HttpServletRequest) req
        );
        if (decision != null && !decision.isGranted()) {
            throw new AccessDeniedException("Access Denied");
        }
        chain.doFilter(req, res);
    }
}
```

**Legacy AccessDecisionManager (still valid for interviews):**
```
┌─────────────────────────┐
│  AccessDecisionManager  │
│  ├── AffirmativeBased   │ → grants if ANY voter grants
│  ├── ConsensusBased     │ → majority vote
│  └── UnanimousBased     │ → ALL voters must grant
└─────────┬───────────────┘
          │
    ┌─────▼──────┐
    │   Voters   │
    ├────────────┤
    │ RoleVoter  │ → checks ROLE_ prefix
    │ AuthVoter  │ → isAuthenticated()
    │ WebExprVoter│→ SpEL expressions
    └────────────┘
```

---

## 2. Authentication Mechanisms

### 2.1 Form-Based Login (Complete Flow)

```
Browser                    Spring Security                     Server
  │                              │                               │
  ├── GET /protected ──────────→│                               │
  │                              ├── AuthorizationFilter: DENY   │
  │                              ├── ExceptionTranslation:       │
  │                              │   saves request to cache      │
  │◄─── 302 /login ─────────────┤   redirects to login          │
  │                              │                               │
  ├── GET /login ───────────────→│                               │
  │◄─── login.html ─────────────┤                               │
  │                              │                               │
  ├── POST /login ──────────────→│                               │
  │   (username, password, csrf) │                               │
  │                              ├── UsernamePasswordAuthFilter  │
  │                              │   extracts credentials        │
  │                              ├── AuthenticationManager       │
  │                              │   → DaoAuthProvider           │
  │                              │   → UserDetailsService        │
  │                              │   → PasswordEncoder.matches() │
  │                              ├── Success:                    │
  │                              │   SecurityContext.setAuth()   │
  │                              │   SecurityContextRepo.save()  │
  │                              │   RequestCache.getRequest()   │
  │◄─── 302 /protected ─────────┤   redirect to saved request  │
  │                              │                               │
  ├── GET /protected ──────────→│                               │
  │                              ├── SecurityContext loaded      │
  │                              ├── AuthorizationFilter: GRANT  │
  │◄─── 200 OK ─────────────────┤                               │
```

```java
@Configuration
@EnableWebSecurity
public class FormLoginConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/public/**").permitAll()
                .requestMatchers("/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            )
            .formLogin(form -> form
                .loginPage("/login")
                .loginProcessingUrl("/login")
                .defaultSuccessUrl("/dashboard", false) // false = use saved request
                .failureUrl("/login?error=true")
                .successHandler(customSuccessHandler())
                .failureHandler(customFailureHandler())
            )
            .build();
    }
    
    @Bean
    public AuthenticationSuccessHandler customSuccessHandler() {
        return (request, response, authentication) -> {
            // Audit log
            auditService.logLogin(authentication.getName(), request.getRemoteAddr());
            // Redirect based on role
            if (authentication.getAuthorities().stream()
                    .anyMatch(a -> a.getAuthority().equals("ROLE_ADMIN"))) {
                response.sendRedirect("/admin/dashboard");
            } else {
                response.sendRedirect("/user/dashboard");
            }
        };
    }
    
    @Bean
    public UserDetailsService userDetailsService(PasswordEncoder encoder) {
        return username -> userRepository.findByUsername(username)
            .map(user -> User.builder()
                .username(user.getUsername())
                .password(user.getPasswordHash())
                .authorities(user.getRoles().stream()
                    .map(r -> new SimpleGrantedAuthority("ROLE_" + r.getName()))
                    .toList())
                .accountLocked(user.isLocked())
                .accountExpired(user.isExpired())
                .credentialsExpired(user.isCredentialsExpired())
                .disabled(!user.isEnabled())
                .build())
            .orElseThrow(() -> new UsernameNotFoundException(username));
    }
    
    @Bean
    public PasswordEncoder passwordEncoder() {
        return PasswordEncoderFactories.createDelegatingPasswordEncoder();
        // Supports: {bcrypt}, {argon2}, {scrypt}, {pbkdf2}
        // Default for new passwords: bcrypt
    }
}
```

### 2.2 HTTP Basic Authentication

```java
@Bean
public SecurityFilterChain apiFilterChain(HttpSecurity http) throws Exception {
    return http
        .securityMatcher("/api/**")
        .authorizeHttpRequests(auth -> auth.anyRequest().authenticated())
        .httpBasic(basic -> basic
            .realmName("API")
            .authenticationEntryPoint((req, res, ex) -> {
                res.setHeader("WWW-Authenticate", "Basic realm=\"API\"");
                res.sendError(HttpServletResponse.SC_UNAUTHORIZED);
            })
        )
        .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
        .csrf(csrf -> csrf.disable())
        .build();
}
```

### 2.3 JWT Token Authentication (Custom Filter)

```java
// Custom JWT Authentication Filter
public class JwtAuthenticationFilter extends OncePerRequestFilter {
    
    private final JwtTokenProvider tokenProvider;
    private final UserDetailsService userDetailsService;
    
    @Override
    protected void doFilterInternal(HttpServletRequest request, 
            HttpServletResponse response, FilterChain chain) throws IOException, ServletException {
        
        String token = extractToken(request);
        
        if (token != null && tokenProvider.validateToken(token)) {
            String username = tokenProvider.getUsernameFromToken(token);
            UserDetails userDetails = userDetailsService.loadUserByUsername(username);
            
            UsernamePasswordAuthenticationToken authentication = 
                new UsernamePasswordAuthenticationToken(
                    userDetails, null, userDetails.getAuthorities());
            authentication.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));
            
            SecurityContextHolder.getContext().setAuthentication(authentication);
        }
        
        chain.doFilter(request, response);
    }
    
    private String extractToken(HttpServletRequest request) {
        String header = request.getHeader("Authorization");
        if (header != null && header.startsWith("Bearer ")) {
            return header.substring(7);
        }
        return null;
    }
    
    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return request.getServletPath().startsWith("/auth/");
    }
}

// JWT Token Provider
@Component
public class JwtTokenProvider {
    
    @Value("${jwt.secret}")
    private String secret;
    
    @Value("${jwt.expiration:3600000}") // 1 hour
    private long expiration;
    
    private SecretKey key;
    
    @PostConstruct
    public void init() {
        this.key = Keys.hmacShaKeyFor(Decoders.BASE64.decode(secret));
    }
    
    public String generateToken(Authentication authentication) {
        UserDetails user = (UserDetails) authentication.getPrincipal();
        Instant now = Instant.now();
        
        return Jwts.builder()
            .subject(user.getUsername())
            .claim("authorities", user.getAuthorities().stream()
                .map(GrantedAuthority::getAuthority)
                .toList())
            .issuedAt(Date.from(now))
            .expiration(Date.from(now.plusMillis(expiration)))
            .signWith(key)
            .compact();
    }
    
    public boolean validateToken(String token) {
        try {
            Jwts.parser().verifyWith(key).build().parseSignedClaims(token);
            return true;
        } catch (JwtException | IllegalArgumentException e) {
            return false;
        }
    }
    
    public String getUsernameFromToken(String token) {
        return Jwts.parser().verifyWith(key).build()
            .parseSignedClaims(token).getPayload().getSubject();
    }
}

// Registration in SecurityFilterChain
@Bean
public SecurityFilterChain jwtFilterChain(HttpSecurity http) throws Exception {
    return http
        .securityMatcher("/api/**")
        .addFilterBefore(new JwtAuthenticationFilter(tokenProvider, userDetailsService),
            UsernamePasswordAuthenticationFilter.class)
        .authorizeHttpRequests(auth -> auth
            .requestMatchers("/api/auth/**").permitAll()
            .anyRequest().authenticated()
        )
        .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
        .csrf(csrf -> csrf.disable())
        .build();
}
```

### 2.4 OAuth2 Login (Authorization Code with PKCE)

```yaml
# application.yml
spring:
  security:
    oauth2:
      client:
        registration:
          google:
            client-id: ${GOOGLE_CLIENT_ID}
            client-secret: ${GOOGLE_CLIENT_SECRET}
            scope: openid, profile, email
            redirect-uri: "{baseUrl}/login/oauth2/code/{registrationId}"
            client-authentication-method: none  # for PKCE
          github:
            client-id: ${GITHUB_CLIENT_ID}
            client-secret: ${GITHUB_CLIENT_SECRET}
            scope: read:user, user:email
        provider:
          custom-oidc:
            issuer-uri: https://auth.example.com
            # Auto-discovers: authorization-uri, token-uri, jwk-set-uri, userinfo-uri
```

```java
@Configuration
@EnableWebSecurity
public class OAuth2LoginConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/", "/login/**", "/error").permitAll()
                .anyRequest().authenticated()
            )
            .oauth2Login(oauth2 -> oauth2
                .loginPage("/login")
                .authorizationEndpoint(auth -> auth
                    .authorizationRequestResolver(pkceResolver())
                )
                .tokenEndpoint(token -> token
                    .accessTokenResponseClient(accessTokenResponseClient())
                )
                .userInfoEndpoint(userInfo -> userInfo
                    .userService(customOAuth2UserService())
                    .oidcUserService(customOidcUserService())
                )
                .successHandler(oAuth2SuccessHandler())
            )
            .build();
    }
    
    // PKCE support
    @Bean
    public OAuth2AuthorizationRequestResolver pkceResolver(
            ClientRegistrationRepository repo) {
        DefaultOAuth2AuthorizationRequestResolver resolver =
            new DefaultOAuth2AuthorizationRequestResolver(repo, "/oauth2/authorization");
        resolver.setAuthorizationRequestCustomizer(
            OAuth2AuthorizationRequestCustomizers.withPkce());
        return resolver;
    }
    
    // Custom user mapping from OAuth2 provider
    @Bean
    public OAuth2UserService<OAuth2UserRequest, OAuth2User> customOAuth2UserService() {
        DefaultOAuth2UserService delegate = new DefaultOAuth2UserService();
        return request -> {
            OAuth2User oAuth2User = delegate.loadUser(request);
            String registrationId = request.getClientRegistration().getRegistrationId();
            
            // Map provider-specific attributes to local user
            Map<String, Object> attributes = oAuth2User.getAttributes();
            String email = extractEmail(registrationId, attributes);
            
            // Create or update local user
            User localUser = userService.findOrCreateFromOAuth2(email, registrationId, attributes);
            
            Set<GrantedAuthority> authorities = localUser.getRoles().stream()
                .map(r -> new SimpleGrantedAuthority("ROLE_" + r))
                .collect(Collectors.toSet());
            
            return new DefaultOAuth2User(authorities, attributes, "email");
        };
    }
}
```

### 2.5 OAuth2 Resource Server

```java
@Configuration
@EnableWebSecurity
public class ResourceServerConfig {

    // JWT-based validation (asymmetric - uses JWK Set)
    @Bean
    public SecurityFilterChain jwtResourceServer(HttpSecurity http) throws Exception {
        return http
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/public/**").permitAll()
                .requestMatchers("/api/admin/**").hasAuthority("SCOPE_admin")
                .anyRequest().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt
                    .decoder(jwtDecoder())
                    .jwtAuthenticationConverter(jwtAuthConverter())
                )
            )
            .build();
    }
    
    @Bean
    public JwtDecoder jwtDecoder() {
        NimbusJwtDecoder decoder = NimbusJwtDecoder
            .withJwkSetUri("https://auth.example.com/.well-known/jwks.json")
            .build();
        
        // Add custom validation
        OAuth2TokenValidator<Jwt> audienceValidator = token -> {
            if (token.getAudience().contains("my-api")) {
                return OAuth2TokenValidatorResult.success();
            }
            return OAuth2TokenValidatorResult.failure(
                new OAuth2Error("invalid_audience", "Expected my-api audience", null));
        };
        
        OAuth2TokenValidator<Jwt> withTimestamp = new DelegatingOAuth2TokenValidator<>(
            JwtValidators.createDefaultWithIssuer("https://auth.example.com"),
            audienceValidator
        );
        decoder.setJwtValidator(withTimestamp);
        return decoder;
    }
    
    // Map JWT claims to Spring Security authorities
    @Bean
    public JwtAuthenticationConverter jwtAuthConverter() {
        JwtGrantedAuthoritiesConverter authoritiesConverter = new JwtGrantedAuthoritiesConverter();
        authoritiesConverter.setAuthoritiesClaimName("roles"); // custom claim
        authoritiesConverter.setAuthorityPrefix("ROLE_");
        
        JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
        converter.setJwtGrantedAuthoritiesConverter(authoritiesConverter);
        return converter;
    }
    
    // Opaque token (introspection-based)
    @Bean
    public SecurityFilterChain opaqueResourceServer(HttpSecurity http) throws Exception {
        return http
            .securityMatcher("/api/v2/**")
            .oauth2ResourceServer(oauth2 -> oauth2
                .opaqueToken(opaque -> opaque
                    .introspectionUri("https://auth.example.com/oauth2/introspect")
                    .introspectionClientCredentials("client-id", "client-secret")
                    .introspector(customIntrospector())
                )
            )
            .build();
    }
    
    @Bean
    public OpaqueTokenIntrospector customIntrospector() {
        OpaqueTokenIntrospector delegate = new NimbusOpaqueTokenIntrospector(
            "https://auth.example.com/oauth2/introspect", "client-id", "client-secret");
        
        return token -> {
            OAuth2AuthenticatedPrincipal principal = delegate.introspect(token);
            // Enrich with local authorities
            return new DefaultOAuth2AuthenticatedPrincipal(
                principal.getName(), principal.getAttributes(), extractAuthorities(principal));
        };
    }
}
```

### 2.6 SAML 2.0

```java
@Configuration
@EnableWebSecurity
public class Saml2Config {

    @Bean
    public SecurityFilterChain samlFilterChain(HttpSecurity http) throws Exception {
        return http
            .authorizeHttpRequests(auth -> auth.anyRequest().authenticated())
            .saml2Login(saml -> saml
                .authenticationManager(new ProviderManager(samlAuthProvider()))
            )
            .saml2Metadata(Customizer.withDefaults())
            .build();
    }
    
    @Bean
    public RelyingPartyRegistrationRepository registrations() {
        RelyingPartyRegistration registration = RelyingPartyRegistrations
            .fromMetadataLocation("https://idp.example.com/metadata.xml")
            .registrationId("idp")
            .entityId("{baseUrl}/saml2/metadata")
            .assertionConsumerServiceLocation("{baseUrl}/login/saml2/sso/{registrationId}")
            .signingX509Credentials(signing -> signing.add(
                Saml2X509Credential.signing(privateKey(), certificate())))
            .decryptionX509Credentials(decrypt -> decrypt.add(
                Saml2X509Credential.decryption(privateKey(), certificate())))
            .build();
        return new InMemoryRelyingPartyRegistrationRepository(registration);
    }
}
```

### 2.7 Remember-Me Authentication

```java
@Bean
public SecurityFilterChain rememberMeChain(HttpSecurity http) throws Exception {
    return http
        .formLogin(Customizer.withDefaults())
        .rememberMe(remember -> remember
            .tokenRepository(persistentTokenRepository()) // DB-backed
            .tokenValiditySeconds(14 * 24 * 3600) // 14 days
            .userDetailsService(userDetailsService)
            .key("unique-secret-key") // for hash-based
            .rememberMeParameter("remember-me")
            .alwaysRemember(false)
        )
        .build();
}

@Bean
public PersistentTokenRepository persistentTokenRepository() {
    JdbcTokenRepositoryImpl repo = new JdbcTokenRepositoryImpl();
    repo.setDataSource(dataSource);
    // Table: persistent_logins (username, series, token, last_used)
    return repo;
}
```

### 2.8 API Key Authentication (Custom)

```java
public class ApiKeyAuthenticationFilter extends OncePerRequestFilter {
    
    private final ApiKeyService apiKeyService;
    
    @Override
    protected void doFilterInternal(HttpServletRequest request, 
            HttpServletResponse response, FilterChain chain) throws IOException, ServletException {
        
        String apiKey = request.getHeader("X-API-Key");
        if (apiKey == null) {
            apiKey = request.getParameter("api_key");
        }
        
        if (apiKey != null) {
            Optional<ApiKeyEntity> key = apiKeyService.validateKey(apiKey);
            if (key.isPresent()) {
                ApiKeyEntity entity = key.get();
                ApiKeyAuthenticationToken auth = new ApiKeyAuthenticationToken(
                    entity.getClientName(), entity.getScopes());
                SecurityContextHolder.getContext().setAuthentication(auth);
            }
        }
        
        chain.doFilter(request, response);
    }
}

// Custom Authentication Token
public class ApiKeyAuthenticationToken extends AbstractAuthenticationToken {
    private final String principal;
    
    public ApiKeyAuthenticationToken(String principal, Collection<String> scopes) {
        super(scopes.stream()
            .map(SimpleGrantedAuthority::new)
            .toList());
        this.principal = principal;
        setAuthenticated(true);
    }
    
    @Override public Object getCredentials() { return null; }
    @Override public Object getPrincipal() { return principal; }
}
```

### 2.9 Certificate-Based (X.509 / mTLS)

```java
@Bean
public SecurityFilterChain x509Chain(HttpSecurity http) throws Exception {
    return http
        .x509(x509 -> x509
            .subjectPrincipalRegex("CN=(.*?)(?:,|$)")
            .userDetailsService(certificateUserDetailsService())
        )
        .authorizeHttpRequests(auth -> auth.anyRequest().authenticated())
        .build();
}

// application.yml for mTLS
// server:
//   ssl:
//     enabled: true
//     key-store: classpath:server.p12
//     key-store-password: ${SSL_KEYSTORE_PASS}
//     trust-store: classpath:truststore.p12
//     trust-store-password: ${SSL_TRUSTSTORE_PASS}
//     client-auth: need  # 'need' = require client cert, 'want' = optional
```

### 2.10 Multi-Factor Authentication

```java
@Component
public class MfaAuthenticationProvider implements AuthenticationProvider {
    
    private final UserDetailsService userDetailsService;
    private final PasswordEncoder passwordEncoder;
    private final TotpService totpService;
    
    @Override
    public Authentication authenticate(Authentication auth) throws AuthenticationException {
        MfaAuthenticationToken mfaToken = (MfaAuthenticationToken) auth;
        String username = mfaToken.getName();
        String password = mfaToken.getCredentials().toString();
        String totpCode = mfaToken.getTotpCode();
        
        UserDetails user = userDetailsService.loadUserByUsername(username);
        
        if (!passwordEncoder.matches(password, user.getPassword())) {
            throw new BadCredentialsException("Invalid password");
        }
        
        if (!totpService.verifyCode(username, totpCode)) {
            throw new BadCredentialsException("Invalid TOTP code");
        }
        
        return new UsernamePasswordAuthenticationToken(user, null, user.getAuthorities());
    }
    
    @Override
    public boolean supports(Class<?> authentication) {
        return MfaAuthenticationToken.class.isAssignableFrom(authentication);
    }
}

@Service
public class TotpService {
    // Uses TOTP (RFC 6238) - typically with Google Authenticator
    public String generateSecret() {
        byte[] buffer = new byte[20];
        new SecureRandom().nextBytes(buffer);
        return Base32.encode(buffer);
    }
    
    public boolean verifyCode(String username, String code) {
        String secret = getUserSecret(username);
        long timeWindow = System.currentTimeMillis() / 30000;
        // Check current window and ±1 for clock drift
        for (int i = -1; i <= 1; i++) {
            String expected = generateTOTP(secret, timeWindow + i);
            if (expected.equals(code)) return true;
        }
        return false;
    }
}
```

---

## 3. OAuth2 & OIDC Deep Dive

### 3.1 Authorization Code Flow with PKCE

```
┌────────┐       ┌───────────────┐       ┌────────────────────┐
│ Browser│       │ Spring Boot   │       │ Authorization      │
│        │       │ (Client)      │       │ Server             │
└───┬────┘       └───────┬───────┘       └─────────┬──────────┘
    │                    │                          │
    │ GET /oauth2/       │                          │
    │ authorization/     │                          │
    │ provider           │                          │
    ├───────────────────→│                          │
    │                    │ Generate:                │
    │                    │  code_verifier (random)  │
    │                    │  code_challenge =        │
    │                    │    SHA256(code_verifier) │
    │                    │  state (CSRF)            │
    │                    │ Store in session         │
    │  302 Redirect      │                          │
    │◄───────────────────┤                          │
    │                    │                          │
    │ GET /authorize?                               │
    │  response_type=code                           │
    │  &client_id=xxx                               │
    │  &redirect_uri=xxx                            │
    │  &scope=openid profile                        │
    │  &state=abc                                   │
    │  &code_challenge=xxx                          │
    │  &code_challenge_method=S256                  │
    ├──────────────────────────────────────────────→│
    │                                               │
    │ (User authenticates + consents)               │
    │                                               │
    │ 302 /login/oauth2/code/provider               │
    │   ?code=AUTH_CODE&state=abc                   │
    │◄──────────────────────────────────────────────┤
    │                    │                          │
    ├───────────────────→│                          │
    │                    │ POST /token              │
    │                    │  grant_type=             │
    │                    │    authorization_code    │
    │                    │  &code=AUTH_CODE         │
    │                    │  &redirect_uri=xxx       │
    │                    │  &code_verifier=xxx      │
    │                    ├─────────────────────────→│
    │                    │                          │
    │                    │  {access_token,          │
    │                    │   refresh_token,         │
    │                    │   id_token}              │
    │                    │◄─────────────────────────┤
    │                    │                          │
    │                    │ GET /userinfo            │
    │                    ├─────────────────────────→│
    │                    │◄─────────────────────────┤
    │                    │                          │
    │ 302 /dashboard     │                          │
    │◄───────────────────┤                          │
```

### 3.2 Client Credentials Flow

```java
// Service-to-service communication
@Configuration
public class ClientCredentialsConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .oauth2Client(Customizer.withDefaults())
            .build();
    }
    
    // WebClient with automatic token management
    @Bean
    public WebClient webClient(OAuth2AuthorizedClientManager authorizedClientManager) {
        ServletOAuth2AuthorizedClientExchangeFilterFunction oauth2 =
            new ServletOAuth2AuthorizedClientExchangeFilterFunction(authorizedClientManager);
        oauth2.setDefaultClientRegistrationId("internal-service");
        
        return WebClient.builder()
            .apply(oauth2.oauth2Configuration())
            .build();
    }
    
    @Bean
    public OAuth2AuthorizedClientManager authorizedClientManager(
            ClientRegistrationRepository clientRegistrationRepository,
            OAuth2AuthorizedClientRepository authorizedClientRepository) {
        
        OAuth2AuthorizedClientProvider authorizedClientProvider =
            OAuth2AuthorizedClientProviderBuilder.builder()
                .clientCredentials()
                .refreshToken()
                .build();
        
        DefaultOAuth2AuthorizedClientManager authorizedClientManager =
            new DefaultOAuth2AuthorizedClientManager(
                clientRegistrationRepository, authorizedClientRepository);
        authorizedClientManager.setAuthorizedClientProvider(authorizedClientProvider);
        
        return authorizedClientManager;
    }
}
```

```yaml
spring:
  security:
    oauth2:
      client:
        registration:
          internal-service:
            provider: auth-server
            client-id: ${SERVICE_CLIENT_ID}
            client-secret: ${SERVICE_CLIENT_SECRET}
            authorization-grant-type: client_credentials
            scope: service.read, service.write
        provider:
          auth-server:
            token-uri: https://auth.example.com/oauth2/token
```

### 3.3 Token Refresh Flow

```java
// Automatic refresh is handled by OAuth2AuthorizedClientProvider
// Manual refresh:
@Service
public class TokenRefreshService {
    
    private final OAuth2AuthorizedClientService clientService;
    private final ClientRegistrationRepository registrationRepo;
    private final RestTemplate restTemplate;
    
    public OAuth2AccessToken refreshToken(String clientRegistrationId, String principalName) {
        OAuth2AuthorizedClient client = clientService
            .loadAuthorizedClient(clientRegistrationId, principalName);
        
        if (client == null || client.getRefreshToken() == null) {
            throw new IllegalStateException("No refresh token available");
        }
        
        ClientRegistration registration = registrationRepo
            .findByRegistrationId(clientRegistrationId);
        
        MultiValueMap<String, String> params = new LinkedMultiValueMap<>();
        params.add("grant_type", "refresh_token");
        params.add("refresh_token", client.getRefreshToken().getTokenValue());
        params.add("client_id", registration.getClientId());
        params.add("client_secret", registration.getClientSecret());
        
        OAuth2AccessTokenResponse response = restTemplate.postForObject(
            registration.getProviderDetails().getTokenUri(),
            new HttpEntity<>(params), OAuth2AccessTokenResponse.class);
        
        return response.getAccessToken();
    }
}
```

### 3.4 JWT Structure and Validation

```
JWT = Header.Payload.Signature

Header (Base64URL):
{
  "alg": "RS256",    // Algorithm: RS256, ES256, PS256
  "typ": "JWT",
  "kid": "key-id-1"  // Key ID for JWK Set lookup
}

Payload (Base64URL):
{
  "iss": "https://auth.example.com",     // Issuer
  "sub": "user-uuid-123",                // Subject
  "aud": ["my-api", "other-api"],        // Audience
  "exp": 1700000000,                     // Expiration
  "iat": 1699996400,                     // Issued At
  "nbf": 1699996400,                     // Not Before
  "jti": "unique-token-id",             // JWT ID (for revocation)
  "scope": "openid profile email",      // Scopes
  "roles": ["ADMIN", "USER"],           // Custom claim
  "tenant_id": "org-123"                // Custom claim
}

Signature:
  RS256(Base64URL(header) + "." + Base64URL(payload), private_key)
```

```java
// Custom JWT decoder with multiple validations
@Bean
public JwtDecoder jwtDecoder() {
    NimbusJwtDecoder decoder = NimbusJwtDecoder
        .withJwkSetUri("https://auth.example.com/.well-known/jwks.json")
        .jwsAlgorithms(algorithms -> {
            algorithms.add(SignatureAlgorithm.RS256);
            algorithms.add(SignatureAlgorithm.ES256);
        })
        .build();
    
    // Cache JWK Set (default: 5 min cache, configurable)
    // The NimbusJwtDecoder handles JWK Set caching internally
    
    OAuth2TokenValidator<Jwt> validator = new DelegatingOAuth2TokenValidator<>(
        JwtValidators.createDefaultWithIssuer("https://auth.example.com"),
        new AudienceValidator("my-api"),
        new TenantValidator()
    );
    decoder.setJwtValidator(validator);
    return decoder;
}

// Custom validator
public class TenantValidator implements OAuth2TokenValidator<Jwt> {
    @Override
    public OAuth2TokenValidatorResult validate(Jwt jwt) {
        String tenantId = jwt.getClaimAsString("tenant_id");
        if (tenantId == null || !tenantRegistry.isActive(tenantId)) {
            return OAuth2TokenValidatorResult.failure(
                new OAuth2Error("invalid_tenant", "Tenant not active", null));
        }
        return OAuth2TokenValidatorResult.success();
    }
}
```

### 3.5 Token Relay in Microservices

```java
// Gateway relays token to downstream services
@Configuration
public class GatewayConfig {
    
    // Spring Cloud Gateway - token relay filter
    @Bean
    public RouteLocator routes(RouteLocatorBuilder builder) {
        return builder.routes()
            .route("user-service", r -> r
                .path("/api/users/**")
                .filters(f -> f.tokenRelay()) // Passes access token downstream
                .uri("lb://user-service"))
            .build();
    }
}

// WebClient with token propagation (non-gateway service)
@Bean
public WebClient webClient(ReactiveOAuth2AuthorizedClientManager clientManager) {
    ServerOAuth2AuthorizedClientExchangeFilterFunction oauth2 =
        new ServerOAuth2AuthorizedClientExchangeFilterFunction(clientManager);
    return WebClient.builder()
        .filter(oauth2)
        .build();
}
```

### 3.6 Custom Claims Mapping

```java
@Bean
public JwtAuthenticationConverter jwtAuthConverter() {
    JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
    converter.setJwtGrantedAuthoritiesConverter(jwt -> {
        Collection<GrantedAuthority> authorities = new ArrayList<>();
        
        // Extract from "scope" claim
        String scope = jwt.getClaimAsString("scope");
        if (scope != null) {
            Arrays.stream(scope.split(" "))
                .map(s -> new SimpleGrantedAuthority("SCOPE_" + s))
                .forEach(authorities::add);
        }
        
        // Extract from "roles" claim (custom)
        List<String> roles = jwt.getClaimAsStringList("roles");
        if (roles != null) {
            roles.stream()
                .map(r -> new SimpleGrantedAuthority("ROLE_" + r))
                .forEach(authorities::add);
        }
        
        // Extract from realm_access.roles (Keycloak format)
        Map<String, Object> realmAccess = jwt.getClaimAsMap("realm_access");
        if (realmAccess != null) {
            List<String> realmRoles = (List<String>) realmAccess.get("roles");
            if (realmRoles != null) {
                realmRoles.stream()
                    .map(r -> new SimpleGrantedAuthority("ROLE_" + r))
                    .forEach(authorities::add);
            }
        }
        
        return authorities;
    });
    
    converter.setPrincipalClaimName("preferred_username"); // default is "sub"
    return converter;
}
```

---

## 4. Authorization

### 4.1 URL-Based Authorization

```java
@Bean
public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
    return http
        .authorizeHttpRequests(auth -> auth
            // Order matters - first match wins
            .requestMatchers("/actuator/health", "/actuator/info").permitAll()
            .requestMatchers("/api/public/**").permitAll()
            .requestMatchers(HttpMethod.POST, "/api/users").hasAuthority("SCOPE_users.write")
            .requestMatchers("/api/admin/**").hasRole("ADMIN")
            .requestMatchers("/api/**").authenticated()
            // Custom authorization manager
            .requestMatchers("/api/tenants/{tenantId}/**").access(tenantAuthManager())
            .anyRequest().denyAll() // deny-by-default
        )
        .build();
}

// Custom AuthorizationManager
@Bean
public AuthorizationManager<RequestAuthorizationContext> tenantAuthManager() {
    return (authentication, context) -> {
        String tenantId = context.getVariables().get("tenantId");
        Authentication auth = authentication.get();
        
        boolean hasAccess = auth.getAuthorities().stream()
            .anyMatch(a -> a.getAuthority().equals("TENANT_" + tenantId));
        
        return new AuthorizationDecision(hasAccess);
    };
}
```

### 4.2 Method-Level Security

```java
@Configuration
@EnableMethodSecurity // replaces @EnableGlobalMethodSecurity
public class MethodSecurityConfig {
}

@Service
public class DocumentService {
    
    @PreAuthorize("hasRole('ADMIN') or #document.ownerId == authentication.name")
    public void updateDocument(Document document) { ... }
    
    @PreAuthorize("@authz.canAccess(authentication, #id, 'document', 'READ')")
    public Document getDocument(Long id) { ... }
    
    @PostAuthorize("returnObject.ownerId == authentication.name or hasRole('ADMIN')")
    public Document findById(Long id) {
        return documentRepository.findById(id).orElseThrow();
    }
    
    @PreFilter("filterObject.tenantId == authentication.principal.tenantId")
    public List<Document> batchSave(List<Document> documents) { ... }
    
    @PostFilter("filterObject.visibility == 'PUBLIC' or filterObject.ownerId == authentication.name")
    public List<Document> findAll() { ... }
    
    // Custom meta-annotation
    @Target(ElementType.METHOD)
    @Retention(RetentionPolicy.RUNTIME)
    @PreAuthorize("hasRole('ADMIN')")
    public @interface AdminOnly {}
    
    @AdminOnly
    public void deleteAll() { ... }
}
```

### 4.3 Custom PermissionEvaluator

```java
@Component
public class CustomPermissionEvaluator implements PermissionEvaluator {
    
    private final PermissionRepository permissionRepository;
    
    @Override
    public boolean hasPermission(Authentication auth, Object targetDomainObject, Object permission) {
        if (auth == null || targetDomainObject == null) return false;
        
        String targetType = targetDomainObject.getClass().getSimpleName().toUpperCase();
        return hasPrivilege(auth, targetType, permission.toString());
    }
    
    @Override
    public boolean hasPermission(Authentication auth, Serializable targetId, 
            String targetType, Object permission) {
        if (auth == null) return false;
        return hasPrivilege(auth, targetType.toUpperCase(), permission.toString());
    }
    
    private boolean hasPrivilege(Authentication auth, String targetType, String permission) {
        return permissionRepository.existsByUsernameAndResourceTypeAndPermission(
            auth.getName(), targetType, permission);
    }
}

// Usage:
@PreAuthorize("hasPermission(#doc, 'WRITE')")
public void update(Document doc) { ... }

@PreAuthorize("hasPermission(#id, 'Document', 'READ')")
public Document get(Long id) { ... }

// Register:
@Bean
public MethodSecurityExpressionHandler expressionHandler(
        CustomPermissionEvaluator evaluator) {
    DefaultMethodSecurityExpressionHandler handler = new DefaultMethodSecurityExpressionHandler();
    handler.setPermissionEvaluator(evaluator);
    return handler;
}
```

### 4.4 Role Hierarchy

```java
@Bean
public RoleHierarchy roleHierarchy() {
    return RoleHierarchyImpl.withDefaultRolePrefix()
        .role("SUPER_ADMIN").implies("ADMIN")
        .role("ADMIN").implies("MANAGER")
        .role("MANAGER").implies("USER")
        .role("USER").implies("GUEST")
        .build();
}

// Spring Security 6 automatically picks this up for method security
// For URL-based, it's automatic when the bean is present
```

### 4.5 Dynamic Authorization (Database-Driven)

```java
@Component
public class DynamicAuthorizationManager implements AuthorizationManager<RequestAuthorizationContext> {
    
    private final PermissionRepository permissionRepository;
    
    @Override
    public AuthorizationDecision check(Supplier<Authentication> authentication, 
            RequestAuthorizationContext context) {
        HttpServletRequest request = context.getRequest();
        String uri = request.getRequestURI();
        String method = request.getMethod();
        Authentication auth = authentication.get();
        
        // Load permissions from DB
        List<UrlPermission> permissions = permissionRepository
            .findByUrlPatternAndMethod(uri, method);
        
        if (permissions.isEmpty()) {
            return new AuthorizationDecision(false); // deny by default
        }
        
        for (UrlPermission perm : permissions) {
            if (auth.getAuthorities().stream()
                    .anyMatch(a -> a.getAuthority().equals(perm.getRequiredAuthority()))) {
                return new AuthorizationDecision(true);
            }
        }
        
        return new AuthorizationDecision(false);
    }
}

@Bean
public SecurityFilterChain filterChain(HttpSecurity http,
        DynamicAuthorizationManager dynamicAuthManager) throws Exception {
    return http
        .authorizeHttpRequests(auth -> auth
            .requestMatchers("/public/**").permitAll()
            .anyRequest().access(dynamicAuthManager)
        )
        .build();
}
```

### 4.6 ABAC (Attribute-Based Access Control)

```java
@Component("authz")
public class AbacAuthorizationService {
    
    public boolean canAccess(Authentication auth, Long resourceId, 
            String resourceType, String action) {
        // Gather subject attributes
        Map<String, Object> subject = extractSubjectAttributes(auth);
        
        // Gather resource attributes
        Map<String, Object> resource = loadResourceAttributes(resourceType, resourceId);
        
        // Gather environment attributes
        Map<String, Object> environment = Map.of(
            "time", LocalTime.now(),
            "ip", getCurrentIp(),
            "dayOfWeek", LocalDate.now().getDayOfWeek()
        );
        
        // Evaluate policies
        return policyEngine.evaluate(subject, resource, environment, action);
    }
    
    private Map<String, Object> extractSubjectAttributes(Authentication auth) {
        Map<String, Object> attrs = new HashMap<>();
        attrs.put("username", auth.getName());
        attrs.put("roles", auth.getAuthorities().stream()
            .map(GrantedAuthority::getAuthority).toList());
        
        if (auth.getPrincipal() instanceof CustomUserDetails user) {
            attrs.put("department", user.getDepartment());
            attrs.put("clearanceLevel", user.getClearanceLevel());
            attrs.put("tenantId", user.getTenantId());
        }
        return attrs;
    }
}

// Usage in SpEL:
@PreAuthorize("@authz.canAccess(authentication, #id, 'Document', 'READ')")
public Document getDocument(Long id) { ... }
```

---

## 5. Security in WebFlux

### 5.1 ReactiveSecurityContextHolder

```java
// WebFlux stores SecurityContext in Reactor Context (not ThreadLocal)
@RestController
public class ReactiveController {
    
    @GetMapping("/me")
    public Mono<String> currentUser() {
        return ReactiveSecurityContextHolder.getContext()
            .map(SecurityContext::getAuthentication)
            .map(Authentication::getName);
    }
}
```

### 5.2 ServerHttpSecurity Configuration

```java
@Configuration
@EnableWebFluxSecurity
@EnableReactiveMethodSecurity
public class WebFluxSecurityConfig {

    @Bean
    public SecurityWebFilterChain securityFilterChain(ServerHttpSecurity http) {
        return http
            .authorizeExchange(exchanges -> exchanges
                .pathMatchers("/actuator/health").permitAll()
                .pathMatchers("/api/public/**").permitAll()
                .pathMatchers("/api/admin/**").hasRole("ADMIN")
                .anyExchange().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt
                    .jwtDecoder(reactiveJwtDecoder())
                    .jwtAuthenticationConverter(reactiveJwtConverter())
                )
            )
            .csrf(csrf -> csrf.disable())
            .cors(cors -> cors.configurationSource(corsConfigSource()))
            .build();
    }
    
    @Bean
    public ReactiveJwtDecoder reactiveJwtDecoder() {
        return NimbusReactiveJwtDecoder
            .withJwkSetUri("https://auth.example.com/.well-known/jwks.json")
            .build();
    }
    
    @Bean
    public Converter<Jwt, Mono<AbstractAuthenticationToken>> reactiveJwtConverter() {
        JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
        converter.setJwtGrantedAuthoritiesConverter(jwt -> {
            List<String> roles = jwt.getClaimAsStringList("roles");
            return roles.stream()
                .map(r -> (GrantedAuthority) new SimpleGrantedAuthority("ROLE_" + r))
                .toList();
        });
        return new ReactiveJwtAuthenticationConverterAdapter(converter);
    }
}
```

### 5.3 Reactive Authentication Manager

```java
@Bean
public ReactiveAuthenticationManager authenticationManager(
        ReactiveUserDetailsService userDetailsService, PasswordEncoder encoder) {
    UserDetailsRepositoryReactiveAuthenticationManager manager =
        new UserDetailsRepositoryReactiveAuthenticationManager(userDetailsService);
    manager.setPasswordEncoder(encoder);
    return manager;
}

@Bean
public ReactiveUserDetailsService userDetailsService(UserRepository userRepo) {
    return username -> userRepo.findByUsername(username)
        .map(user -> User.builder()
            .username(user.getUsername())
            .password(user.getPassword())
            .authorities(user.getRoles().toArray(new String[0]))
            .build());
}
```

### 5.4 Context Propagation for Security

```java
// Problem: SecurityContext lost across reactive boundaries
// Solution: Reactor Context propagation

@Service
public class ReactiveService {
    
    public Mono<Document> processDocument(Long id) {
        return ReactiveSecurityContextHolder.getContext()
            .flatMap(ctx -> {
                Authentication auth = ctx.getAuthentication();
                return documentRepo.findById(id)
                    .filter(doc -> doc.getOwnerId().equals(auth.getName()));
            });
    }
}

// WebClient with token propagation in WebFlux
@Bean
public WebClient webClient(ReactiveOAuth2AuthorizedClientManager clientManager) {
    ServerOAuth2AuthorizedClientExchangeFilterFunction filter =
        new ServerOAuth2AuthorizedClientExchangeFilterFunction(clientManager);
    filter.setDefaultOAuth2AuthorizedClient(true);
    
    return WebClient.builder()
        .filter(filter)
        .build();
}
```

### 5.5 Custom Reactive Security Filter

```java
@Component
public class ReactiveApiKeyFilter implements WebFilter {
    
    private final ApiKeyService apiKeyService;
    
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        String apiKey = exchange.getRequest().getHeaders().getFirst("X-API-Key");
        
        if (apiKey == null) {
            return chain.filter(exchange);
        }
        
        return apiKeyService.validate(apiKey)
            .flatMap(principal -> {
                Authentication auth = new ApiKeyAuthenticationToken(
                    principal.getName(), principal.getAuthorities());
                SecurityContext context = new SecurityContextImpl(auth);
                return chain.filter(exchange)
                    .contextWrite(ReactiveSecurityContextHolder.withSecurityContext(
                        Mono.just(context)));
            })
            .switchIfEmpty(chain.filter(exchange));
    }
}
```

---

## 6. Common Vulnerabilities & Prevention

### 6.1 CSRF Protection

```java
@Bean
public SecurityFilterChain csrfConfig(HttpSecurity http) throws Exception {
    return http
        .csrf(csrf -> csrf
            // SPA-friendly: use cookie-based token
            .csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse())
            .csrfTokenRequestHandler(new SpaCsrfTokenRequestHandler())
            // Ignore for stateless APIs
            .ignoringRequestMatchers("/api/webhooks/**")
        )
        .build();
}

// SPA CSRF handler (Spring Security 6)
public class SpaCsrfTokenRequestHandler extends CsrfTokenRequestAttributeHandler {
    private final CsrfTokenRequestHandler delegate = new XorCsrfTokenRequestAttributeHandler();
    
    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response,
            Supplier<CsrfToken> csrfToken) {
        this.delegate.handle(request, response, csrfToken);
    }
    
    @Override
    public String resolveCsrfTokenValue(HttpServletRequest request, CsrfToken csrfToken) {
        String header = request.getHeader(csrfToken.getHeaderName());
        return (header != null) 
            ? super.resolveCsrfTokenValue(request, csrfToken) 
            : this.delegate.resolveCsrfTokenValue(request, csrfToken);
    }
}
```

**Double Submit Cookie Pattern:**
```
1. Server sets CSRF token in cookie: XSRF-TOKEN=abc123
2. JavaScript reads cookie, sends in header: X-XSRF-TOKEN: abc123
3. Server validates header matches cookie
4. Attacker can't read cross-origin cookies → can't forge header
```

### 6.2 XSS Prevention

```java
@Bean
public SecurityFilterChain securityHeaders(HttpSecurity http) throws Exception {
    return http
        .headers(headers -> headers
            .contentSecurityPolicy(csp -> csp
                .policyDirectives(
                    "default-src 'self'; " +
                    "script-src 'self' 'nonce-{random}'; " +
                    "style-src 'self' 'unsafe-inline'; " +
                    "img-src 'self' data: https:; " +
                    "connect-src 'self' https://api.example.com; " +
                    "frame-ancestors 'none'; " +
                    "form-action 'self'")
            )
            .xssProtection(xss -> xss.headerValue(
                XXssProtectionHeaderWriter.HeaderValue.ENABLED_MODE_BLOCK))
            .contentTypeOptions(Customizer.withDefaults()) // X-Content-Type-Options: nosniff
        )
        .build();
}
```

### 6.3 CORS Configuration

```java
@Bean
public CorsConfigurationSource corsConfigurationSource() {
    CorsConfiguration config = new CorsConfiguration();
    config.setAllowedOrigins(List.of("https://app.example.com"));
    config.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "OPTIONS"));
    config.setAllowedHeaders(List.of("Authorization", "Content-Type", "X-XSRF-TOKEN"));
    config.setExposedHeaders(List.of("X-Total-Count"));
    config.setAllowCredentials(true);
    config.setMaxAge(3600L);
    
    UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
    source.registerCorsConfiguration("/api/**", config);
    return source;
}

@Bean
public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
    return http
        .cors(cors -> cors.configurationSource(corsConfigurationSource()))
        .build();
}
```

### 6.4 Session Fixation

```java
@Bean
public SecurityFilterChain sessionConfig(HttpSecurity http) throws Exception {
    return http
        .sessionManagement(session -> session
            .sessionFixation().changeSessionId() // default in Spring Security 6
            // Options: newSession(), migrateSession(), changeSessionId(), none()
            .maximumSessions(1)
            .maxSessionsPreventsLogin(true) // reject new login vs expire old
            .sessionRegistry(sessionRegistry())
        )
        .build();
}
```

### 6.5 Security Headers (Complete)

```java
@Bean
public SecurityFilterChain allHeaders(HttpSecurity http) throws Exception {
    return http
        .headers(headers -> headers
            // HSTS - force HTTPS
            .httpStrictTransportSecurity(hsts -> hsts
                .maxAgeInSeconds(31536000)
                .includeSubDomains(true)
                .preload(true))
            // Prevent clickjacking
            .frameOptions(frame -> frame.deny())
            // Prevent MIME sniffing
            .contentTypeOptions(Customizer.withDefaults())
            // CSP
            .contentSecurityPolicy(csp -> csp
                .policyDirectives("default-src 'self'"))
            // Permissions Policy
            .permissionsPolicy(pp -> pp
                .policy("geolocation=(), camera=(), microphone=()"))
            // Referrer Policy
            .referrerPolicy(ref -> ref
                .policy(ReferrerPolicyHeaderWriter.ReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN))
        )
        .build();
}
```

### 6.6 OWASP Top 10 in Spring Boot Context

| # | Vulnerability | Spring Boot Mitigation |
|---|---|---|
| A01 | Broken Access Control | `@PreAuthorize`, `AuthorizationManager`, deny-by-default |
| A02 | Cryptographic Failures | BCrypt/Argon2, TLS everywhere, Vault for secrets |
| A03 | Injection | Spring Data parameterized queries, input validation |
| A04 | Insecure Design | Threat modeling, security requirements in design |
| A05 | Security Misconfiguration | `SecurityFilterChain` defaults, actuator security |
| A06 | Vulnerable Components | Dependabot, OWASP dependency-check plugin |
| A07 | Auth Failures | Rate limiting, MFA, account lockout |
| A08 | Data Integrity Failures | CSRF protection, signed JWTs, integrity checks |
| A09 | Logging Failures | Audit logging, alerting on auth failures |
| A10 | SSRF | URL validation, allowlists, network segmentation |

---

## 7. Production Security Patterns

### 7.1 Zero Trust Architecture with Spring Boot

```
┌─────────────────────────────────────────────────────────────┐
│                    Zero Trust Principles                      │
│  • Never trust, always verify                                │
│  • Assume breach                                             │
│  • Verify explicitly (every request)                         │
│  • Use least privilege                                       │
│  • Micro-segmentation                                        │
└─────────────────────────────────────────────────────────────┘

                    ┌─────────────┐
                    │  API Gateway │
                    │  (TLS term,  │
                    │   rate limit,│
                    │   WAF)       │
                    └──────┬──────┘
                           │ mTLS
            ┌──────────────┼──────────────┐
            │              │              │
    ┌───────▼──────┐ ┌────▼─────┐ ┌─────▼──────┐
    │ Service A    │ │Service B │ │ Service C  │
    │ (validates   │ │(validates│ │(validates  │
    │  JWT on      │ │ JWT on   │ │ JWT on     │
    │  EVERY req)  │ │ EVERY req│ │ EVERY req) │
    └──────────────┘ └──────────┘ └────────────┘
         Each service:
         • Validates token (not just trusts gateway)
         • Enforces own authorization
         • Uses short-lived tokens
         • Logs all access
```

```java
// Zero Trust: validate everything at each service
@Configuration
public class ZeroTrustConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .oauth2ResourceServer(oauth2 -> oauth2.jwt(jwt -> jwt
                .decoder(jwtDecoder())
                .jwtAuthenticationConverter(jwtConverter())
            ))
            .authorizeHttpRequests(auth -> auth
                .anyRequest().authenticated()
            )
            // Additional request validation
            .addFilterAfter(new RequestIntegrityFilter(), BearerTokenAuthenticationFilter.class)
            .build();
    }
}

// Validate request integrity (signed requests, timestamp freshness)
public class RequestIntegrityFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request, 
            HttpServletResponse response, FilterChain chain) throws IOException, ServletException {
        
        // Check request timestamp (prevent replay)
        String timestamp = request.getHeader("X-Request-Timestamp");
        if (timestamp != null) {
            Instant requestTime = Instant.parse(timestamp);
            if (Duration.between(requestTime, Instant.now()).abs().toSeconds() > 30) {
                response.sendError(HttpServletResponse.SC_BAD_REQUEST, "Request too old");
                return;
            }
        }
        
        chain.doFilter(request, response);
    }
}
```

### 7.2 Service-to-Service Authentication (mTLS + JWT)

```java
// mTLS configuration for service mesh
@Configuration
public class MtlsConfig {
    
    @Bean
    public WebClient serviceClient() {
        SslContext sslContext = SslContextBuilder.forClient()
            .keyManager(loadKeyManager())   // This service's cert
            .trustManager(loadTrustManager()) // CA trust chain
            .build();
        
        HttpClient httpClient = HttpClient.create()
            .secure(spec -> spec.sslContext(sslContext));
        
        return WebClient.builder()
            .clientConnector(new ReactorClientHttpConnector(httpClient))
            .defaultHeader("Authorization", "Bearer " + getServiceToken())
            .build();
    }
}
```

### 7.3 API Gateway Security Patterns

```java
// Spring Cloud Gateway security
@Configuration
public class GatewaySecurityConfig {

    @Bean
    public SecurityWebFilterChain gatewayFilterChain(ServerHttpSecurity http) {
        return http
            .authorizeExchange(exchanges -> exchanges
                .pathMatchers("/auth/**").permitAll()
                .pathMatchers("/api/admin/**").hasRole("ADMIN")
                .anyExchange().authenticated()
            )
            .oauth2Login(Customizer.withDefaults())
            .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
            .build();
    }
    
    // Rate limiting
    @Bean
    public KeyResolver userKeyResolver() {
        return exchange -> ReactiveSecurityContextHolder.getContext()
            .map(ctx -> ctx.getAuthentication().getName())
            .defaultIfEmpty(exchange.getRequest().getRemoteAddress().getHostString());
    }
}
```

```yaml
spring:
  cloud:
    gateway:
      routes:
        - id: user-service
          uri: lb://user-service
          predicates:
            - Path=/api/users/**
          filters:
            - TokenRelay=
            - name: RequestRateLimiter
              args:
                redis-rate-limiter.replenishRate: 10
                redis-rate-limiter.burstCapacity: 20
                key-resolver: "#{@userKeyResolver}"
            - RemoveRequestHeader=Cookie
            - StripPrefix=1
```

### 7.4 Token Revocation Strategies

```java
// Strategy 1: Short-lived tokens + refresh token rotation
// Access token: 5 min, Refresh token: 7 days (rotated on each use)

// Strategy 2: Token blacklist (Redis)
@Component
public class TokenBlacklistService {
    private final RedisTemplate<String, String> redis;
    
    public void revoke(String jti, Instant expiration) {
        Duration ttl = Duration.between(Instant.now(), expiration);
        redis.opsForValue().set("blacklist:" + jti, "revoked", ttl);
    }
    
    public boolean isRevoked(String jti) {
        return Boolean.TRUE.equals(redis.hasKey("blacklist:" + jti));
    }
}

// Custom JWT validator that checks blacklist
@Bean
public OAuth2TokenValidator<Jwt> blacklistValidator(TokenBlacklistService blacklist) {
    return token -> {
        if (blacklist.isRevoked(token.getId())) {
            return OAuth2TokenValidatorResult.failure(
                new OAuth2Error("token_revoked", "Token has been revoked", null));
        }
        return OAuth2TokenValidatorResult.success();
    };
}
```

### 7.5 Rate Limiting

```java
// Using Bucket4j + Spring Boot
@Configuration
public class RateLimitConfig {
    
    @Bean
    public FilterRegistrationBean<RateLimitFilter> rateLimitFilter() {
        FilterRegistrationBean<RateLimitFilter> reg = new FilterRegistrationBean<>();
        reg.setFilter(new RateLimitFilter(proxyManager));
        reg.addUrlPatterns("/api/*");
        reg.setOrder(Ordered.HIGHEST_PRECEDENCE);
        return reg;
    }
}

public class RateLimitFilter extends OncePerRequestFilter {
    
    private final ProxyManager<String> proxyManager;
    
    @Override
    protected void doFilterInternal(HttpServletRequest request,
            HttpServletResponse response, FilterChain chain) throws IOException, ServletException {
        
        String key = resolveKey(request);
        BucketConfiguration config = BucketConfiguration.builder()
            .addLimit(Bandwidth.builder()
                .capacity(100)
                .refillGreedy(100, Duration.ofMinutes(1))
                .build())
            .build();
        
        Bucket bucket = proxyManager.builder().build(key, () -> config);
        ConsumptionProbe probe = bucket.tryConsumeAndReturnRemaining(1);
        
        if (probe.isConsumed()) {
            response.setHeader("X-Rate-Limit-Remaining", 
                String.valueOf(probe.getRemainingTokens()));
            chain.doFilter(request, response);
        } else {
            response.setStatus(429);
            response.setHeader("Retry-After", 
                String.valueOf(probe.getNanosToWaitForRefill() / 1_000_000_000));
            response.getWriter().write("{\"error\":\"rate_limit_exceeded\"}");
        }
    }
    
    private String resolveKey(HttpServletRequest request) {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.isAuthenticated()) {
            return "user:" + auth.getName();
        }
        return "ip:" + request.getRemoteAddr();
    }
}
```

### 7.6 Audit Logging

```java
@Component
@Aspect
public class SecurityAuditAspect {
    
    private final AuditEventRepository auditRepository;
    
    @AfterReturning("@annotation(org.springframework.security.access.prepost.PreAuthorize)")
    public void auditSuccess(JoinPoint joinPoint) {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        auditRepository.add(new AuditEvent(
            auth.getName(),
            "AUTHORIZATION_SUCCESS",
            Map.of(
                "method", joinPoint.getSignature().toShortString(),
                "args", Arrays.toString(joinPoint.getArgs()),
                "timestamp", Instant.now().toString()
            )
        ));
    }
    
    @AfterThrowing(value = "@annotation(org.springframework.security.access.prepost.PreAuthorize)", 
                   throwing = "ex")
    public void auditFailure(JoinPoint joinPoint, AccessDeniedException ex) {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        auditRepository.add(new AuditEvent(
            auth != null ? auth.getName() : "anonymous",
            "AUTHORIZATION_FAILURE",
            Map.of(
                "method", joinPoint.getSignature().toShortString(),
                "reason", ex.getMessage(),
                "timestamp", Instant.now().toString()
            )
        ));
    }
}

// Spring Boot Actuator audit events
@Component
public class AuthenticationAuditListener {
    
    @EventListener
    public void onAuthSuccess(AuthenticationSuccessEvent event) {
        log.info("AUTH_SUCCESS user={} authorities={}", 
            event.getAuthentication().getName(),
            event.getAuthentication().getAuthorities());
    }
    
    @EventListener
    public void onAuthFailure(AbstractAuthenticationFailureEvent event) {
        log.warn("AUTH_FAILURE user={} exception={}", 
            event.getAuthentication().getName(),
            event.getException().getClass().getSimpleName());
    }
}
```

### 7.7 Secrets Management

```java
// Spring Cloud Vault integration
// bootstrap.yml:
// spring:
//   cloud:
//     vault:
//       uri: https://vault.example.com
//       authentication: KUBERNETES  # or TOKEN, APPROLE, AWS_IAM
//       kubernetes:
//         role: my-service
//       kv:
//         enabled: true
//         backend: secret

@Configuration
public class VaultConfig {
    
    // Secrets auto-injected as properties:
    @Value("${db.password}") // from Vault KV: secret/my-service/db.password
    private String dbPassword;
    
    // Dynamic database credentials (leased)
    @Bean
    public DataSource dataSource(VaultOperations vault) {
        VaultResponse response = vault.read("database/creds/my-role");
        Map<String, Object> data = response.getData();
        
        HikariDataSource ds = new HikariDataSource();
        ds.setUsername((String) data.get("username"));
        ds.setPassword((String) data.get("password"));
        // Lease renewal handled by Spring Cloud Vault
        return ds;
    }
}

// AWS Secrets Manager alternative:
// spring:
//   config:
//     import: aws-secretsmanager:/prod/my-service/
```

### 7.8 Encryption at Rest and in Transit

```java
// Attribute-level encryption with JPA
@Entity
public class User {
    @Id
    private Long id;
    
    private String username;
    
    @Convert(converter = EncryptedStringConverter.class)
    private String ssn; // encrypted in DB
    
    @Convert(converter = EncryptedStringConverter.class)
    private String email;
}

@Converter
public class EncryptedStringConverter implements AttributeConverter<String, String> {
    
    private final AesEncryptionService encryptionService;
    
    @Override
    public String convertToDatabaseColumn(String attribute) {
        return attribute != null ? encryptionService.encrypt(attribute) : null;
    }
    
    @Override
    public String convertToEntityAttribute(String dbData) {
        return dbData != null ? encryptionService.decrypt(dbData) : null;
    }
}

@Service
public class AesEncryptionService {
    private final SecretKey key; // loaded from Vault/KMS
    
    public String encrypt(String plainText) {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        byte[] iv = new byte[12];
        SecureRandom.getInstanceStrong().nextBytes(iv);
        cipher.init(Cipher.ENCRYPT_MODE, key, new GCMParameterSpec(128, iv));
        byte[] encrypted = cipher.doFinal(plainText.getBytes(UTF_8));
        // Prepend IV to ciphertext
        byte[] combined = ByteBuffer.allocate(iv.length + encrypted.length)
            .put(iv).put(encrypted).array();
        return Base64.getEncoder().encodeToString(combined);
    }
    
    public String decrypt(String cipherText) {
        byte[] combined = Base64.getDecoder().decode(cipherText);
        ByteBuffer buffer = ByteBuffer.wrap(combined);
        byte[] iv = new byte[12];
        buffer.get(iv);
        byte[] encrypted = new byte[buffer.remaining()];
        buffer.get(encrypted);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(128, iv));
        return new String(cipher.doFinal(encrypted), UTF_8);
    }
}
```

---

## Interview Questions & Answers

**Q: What happens when SecurityContextPersistenceFilter is removed in Spring Security 6?**
A: Replaced by `SecurityContextHolderFilter` which uses deferred/lazy loading and requires explicit save. This prevents accidental session creation and is more aligned with stateless architectures.

**Q: How does Spring Security handle multiple SecurityFilterChains?**
A: `FilterChainProxy` iterates through chains in order, using the first matching `RequestMatcher`. Chains with specific matchers should come before generic ones.

**Q: Explain the difference between `@PreAuthorize` and `@Secured`.**
A: `@Secured` only supports role names (simple string matching). `@PreAuthorize` supports SpEL expressions enabling complex logic: `hasRole('X') and #arg.owner == authentication.name`.

**Q: How does OAuth2 token relay work in a microservices architecture?**
A: The gateway extracts the access token from the authenticated user's session, attaches it as a Bearer token to downstream requests. Spring Cloud Gateway's `TokenRelay` filter automates this.

**Q: How do you implement token revocation with JWTs?**
A: JWTs are stateless so you need: (1) short-lived access tokens (5 min), (2) refresh token rotation with revocation list, (3) optional: JTI-based blacklist in Redis with TTL matching token expiration.

**Q: Why is SecurityContext stored in ThreadLocal problematic for reactive?**
A: Reactive uses a small thread pool with thread switching between operators. ThreadLocal would lose context. WebFlux uses Reactor's `Context` (subscriber context) via `ReactiveSecurityContextHolder`.

**Q: How do you implement Zero Trust between Spring Boot microservices?**
A: (1) mTLS for transport, (2) JWT validation at EVERY service (not just gateway), (3) short-lived service tokens via client_credentials, (4) least-privilege scopes, (5) network segmentation, (6) audit everything.
