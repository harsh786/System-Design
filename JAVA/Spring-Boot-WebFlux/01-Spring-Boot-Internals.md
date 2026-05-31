# Spring Boot Internals - End-to-End Deep Dive

## Table of Contents
- [Bootstrap Process](#bootstrap-process)
- [Auto-Configuration Mechanism](#auto-configuration-mechanism)
- [Bean Lifecycle](#bean-lifecycle)
- [Request Processing Pipeline](#request-processing-pipeline)
- [Embedded Server Architecture](#embedded-server-architecture)
- [Dependency Injection Internals](#dependency-injection-internals)
- [Spring Boot Starter Mechanism](#spring-boot-starter-mechanism)
- [Actuator Internals](#actuator-internals)

---

## Bootstrap Process

### Q1: What happens when you call `SpringApplication.run()`?

**Complete E2E Flow:**

```
main() → SpringApplication.run()
    ├── 1. Create SpringApplication instance
    │   ├── Detect WebApplicationType (SERVLET, REACTIVE, NONE)
    │   ├── Load ApplicationContextInitializers (from spring.factories)
    │   └── Load ApplicationListeners (from spring.factories)
    │
    ├── 2. Run method execution
    │   ├── Create & start StopWatch
    │   ├── Configure headless property
    │   ├── Get SpringApplicationRunListeners
    │   ├── Publish ApplicationStartingEvent
    │   ├── Prepare Environment
    │   │   ├── Create Environment (StandardServletEnvironment / StandardReactiveWebEnvironment)
    │   │   ├── Configure Environment (command line args, profiles)
    │   │   └── Publish ApplicationEnvironmentPreparedEvent
    │   │
    │   ├── Print Banner
    │   ├── Create ApplicationContext
    │   │   ├── SERVLET → AnnotationConfigServletWebServerApplicationContext
    │   │   ├── REACTIVE → AnnotationConfigReactiveWebServerApplicationContext
    │   │   └── NONE → AnnotationConfigApplicationContext
    │   │
    │   ├── Prepare Context
    │   │   ├── Set Environment
    │   │   ├── Post-process ApplicationContext
    │   │   ├── Apply Initializers
    │   │   ├── Publish ApplicationContextInitializedEvent
    │   │   ├── Register main class as bean definition
    │   │   └── Publish ApplicationPreparedEvent
    │   │
    │   ├── Refresh Context (THE MOST CRITICAL STEP)
    │   │   ├── prepareRefresh()
    │   │   ├── obtainFreshBeanFactory()
    │   │   ├── prepareBeanFactory()
    │   │   ├── postProcessBeanFactory()
    │   │   ├── invokeBeanFactoryPostProcessors()
    │   │   │   └── ConfigurationClassPostProcessor scans @ComponentScan, @Import, @Bean
    │   │   ├── registerBeanPostProcessors()
    │   │   ├── initMessageSource()
    │   │   ├── initApplicationEventMulticaster()
    │   │   ├── onRefresh() → CREATE EMBEDDED WEB SERVER
    │   │   ├── registerListeners()
    │   │   ├── finishBeanFactoryInitialization() → INSTANTIATE ALL SINGLETONS
    │   │   └── finishRefresh() → START EMBEDDED WEB SERVER
    │   │
    │   ├── Publish ApplicationStartedEvent
    │   ├── Call ApplicationRunner & CommandLineRunner
    │   └── Publish ApplicationReadyEvent
    │
    └── Return ConfigurableApplicationContext
```

**Deep Explanation:**

```java
// Simplified SpringApplication.run() internals
public ConfigurableApplicationContext run(String... args) {
    StopWatch stopWatch = new StopWatch();
    stopWatch.start();
    
    ConfigurableApplicationContext context = null;
    
    // Step 1: Get run listeners (SpringApplicationRunListener implementations)
    SpringApplicationRunListeners listeners = getRunListeners(args);
    listeners.starting(); // ApplicationStartingEvent
    
    try {
        // Step 2: Prepare environment
        ApplicationArguments applicationArguments = new DefaultApplicationArguments(args);
        ConfigurableEnvironment environment = prepareEnvironment(listeners, applicationArguments);
        
        // Step 3: Create the ApplicationContext
        context = createApplicationContext();
        
        // Step 4: Prepare the context
        prepareContext(context, environment, listeners, applicationArguments);
        
        // Step 5: Refresh the context (most important)
        refreshContext(context);
        
        // Step 6: After refresh
        afterRefresh(context, applicationArguments);
        
        listeners.started(context); // ApplicationStartedEvent
        callRunners(context, applicationArguments);
        listeners.running(context); // ApplicationReadyEvent
        
    } catch (Throwable ex) {
        handleRunFailure(context, ex, listeners);
        throw new IllegalStateException(ex);
    }
    
    return context;
}
```

---

### Q2: How does Spring Boot detect if it should start as SERVLET, REACTIVE, or NONE?

**Answer:**

```java
// WebApplicationType detection logic
static WebApplicationType deduceFromClasspath() {
    // Check for REACTIVE
    if (ClassUtils.isPresent(WEBFLUX_INDICATOR_CLASS, null) 
        && !ClassUtils.isPresent(WEBMVC_INDICATOR_CLASS, null)
        && !ClassUtils.isPresent(JERSEY_INDICATOR_CLASS, null)) {
        return WebApplicationType.REACTIVE;
    }
    
    // Check for NONE (no web at all)
    for (String className : SERVLET_INDICATOR_CLASSES) {
        if (!ClassUtils.isPresent(className, null)) {
            return WebApplicationType.NONE;
        }
    }
    
    // Default to SERVLET
    return WebApplicationType.SERVLET;
}
```

**Key classes checked:**
- `WEBFLUX_INDICATOR_CLASS` = `org.springframework.web.reactive.DispatcherHandler`
- `WEBMVC_INDICATOR_CLASS` = `org.springframework.web.servlet.DispatcherServlet`
- `SERVLET_INDICATOR_CLASSES` = `javax.servlet.Servlet`, `org.springframework.web.context.ConfigurableWebApplicationContext`

---

### Q3: What is the role of `spring.factories` file?

**Answer:**

`spring.factories` (located in `META-INF/`) is the backbone of Spring Boot's auto-configuration. It uses Java's `ServiceLoader`-like mechanism.

```properties
# META-INF/spring.factories
org.springframework.boot.autoconfigure.EnableAutoConfiguration=\
  org.springframework.boot.autoconfigure.web.servlet.WebMvcAutoConfiguration,\
  org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration,\
  org.springframework.boot.autoconfigure.orm.jpa.HibernateJpaAutoConfiguration

org.springframework.context.ApplicationContextInitializer=\
  org.springframework.boot.context.ConfigurationWarningsApplicationContextInitializer

org.springframework.context.ApplicationListener=\
  org.springframework.boot.context.config.ConfigFileApplicationListener
```

**In Spring Boot 3.x**, this moved to `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`

---

## Auto-Configuration Mechanism

### Q4: How does `@EnableAutoConfiguration` work internally?

**Answer:**

```
@SpringBootApplication
  └── @EnableAutoConfiguration
        └── @Import(AutoConfigurationImportSelector.class)
              └── selectImports() method
                    ├── Load all candidates from spring.factories / AutoConfiguration.imports
                    ├── Remove duplicates
                    ├── Apply exclusions (@SpringBootApplication(exclude=...))
                    ├── Filter by @ConditionalOn* annotations
                    └── Return final list of configuration classes
```

**Detailed flow:**

```java
public class AutoConfigurationImportSelector implements DeferredImportSelector {
    
    @Override
    public String[] selectImports(AnnotationMetadata metadata) {
        // 1. Load all auto-configuration candidates
        List<String> configurations = getCandidateConfigurations(metadata, attributes);
        // Loads from META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports
        
        // 2. Remove duplicates
        configurations = removeDuplicates(configurations);
        
        // 3. Apply exclusions
        Set<String> exclusions = getExclusions(metadata, attributes);
        configurations.removeAll(exclusions);
        
        // 4. Filter (OnClassCondition, OnBeanCondition, etc.)
        configurations = getConfigurationClassFilter().filter(configurations);
        
        return configurations.toArray(new String[0]);
    }
}
```

### Q5: Explain all `@ConditionalOn*` annotations and their evaluation order

**Answer:**

| Annotation | Condition | Phase |
|-----------|-----------|-------|
| `@ConditionalOnClass` | Class present on classpath | Early (filter phase) |
| `@ConditionalOnMissingClass` | Class NOT on classpath | Early (filter phase) |
| `@ConditionalOnBean` | Bean exists in context | Late (parse phase) |
| `@ConditionalOnMissingBean` | Bean NOT in context | Late (parse phase) |
| `@ConditionalOnProperty` | Property has specific value | Early |
| `@ConditionalOnResource` | Resource exists on classpath | Early |
| `@ConditionalOnWebApplication` | Is web app | Early |
| `@ConditionalOnNotWebApplication` | Is NOT web app | Early |
| `@ConditionalOnExpression` | SpEL expression is true | Late |
| `@ConditionalOnJava` | Java version matches | Early |
| `@ConditionalOnSingleCandidate` | Single bean candidate | Late |

**Evaluation Order (Critical for interviews):**

```
1. @ConditionalOnClass / @ConditionalOnMissingClass (FILTER phase - before parsing)
2. @ConditionalOnProperty (early evaluation)
3. @ConditionalOnResource
4. @ConditionalOnWebApplication / @ConditionalOnNotWebApplication
5. @ConditionalOnBean / @ConditionalOnMissingBean (LATE - depends on bean registration order)
```

**Why order matters:**
```java
// This can FAIL because bean conditions depend on registration order
@Configuration
@ConditionalOnBean(DataSource.class)  // May not find it if DataSource not yet registered
public class MyConfig { }

// SOLUTION: Use @AutoConfigureAfter
@Configuration
@AutoConfigureAfter(DataSourceAutoConfiguration.class)
@ConditionalOnBean(DataSource.class)
public class MyConfig { }
```

---

## Bean Lifecycle

### Q6: Complete Bean Lifecycle in Spring

```
1.  Bean Definition Loading (from @Component, @Bean, XML)
2.  BeanFactoryPostProcessor.postProcessBeanFactory()
     └── Modify bean definitions BEFORE instantiation
3.  Bean Instantiation (constructor)
4.  Populate Properties (dependency injection via @Autowired, @Value)
5.  BeanNameAware.setBeanName()
6.  BeanClassLoaderAware.setBeanClassLoader()
7.  BeanFactoryAware.setBeanFactory()
8.  EnvironmentAware.setEnvironment()
9.  EmbeddedValueResolverAware.setEmbeddedValueResolver()
10. ResourceLoaderAware.setResourceLoader()
11. ApplicationEventPublisherAware.setApplicationEventPublisher()
12. MessageSourceAware.setMessageSource()
13. ApplicationContextAware.setApplicationContext()
14. ServletContextAware.setServletContext() (web only)
15. BeanPostProcessor.postProcessBeforeInitialization() (ALL BPPs)
16. @PostConstruct method
17. InitializingBean.afterPropertiesSet()
18. Custom init-method (from @Bean(initMethod="..."))
19. BeanPostProcessor.postProcessAfterInitialization() (ALL BPPs)
     └── This is where AOP proxies are created!
20. Bean is READY for use
     ...
21. @PreDestroy method
22. DisposableBean.destroy()
23. Custom destroy-method (from @Bean(destroyMethod="..."))
```

### Q7: What are BeanPostProcessors and how do they enable AOP?

**Answer:**

```java
public interface BeanPostProcessor {
    // Called BEFORE init methods (@PostConstruct, afterPropertiesSet)
    default Object postProcessBeforeInitialization(Object bean, String beanName) {
        return bean;
    }
    
    // Called AFTER init methods - THIS IS WHERE PROXIES ARE CREATED
    default Object postProcessAfterInitialization(Object bean, String beanName) {
        return bean; // Can return a proxy wrapping the original bean
    }
}
```

**AOP Proxy Creation:**

```java
// AbstractAutoProxyCreator (extends BeanPostProcessor)
public Object postProcessAfterInitialization(Object bean, String beanName) {
    if (bean != null) {
        Object cacheKey = getCacheKey(bean.getClass(), beanName);
        if (!this.earlyProxyReferences.contains(cacheKey)) {
            return wrapIfNecessary(bean, beanName, cacheKey);
            // Creates JDK dynamic proxy or CGLIB proxy
        }
    }
    return bean;
}
```

**JDK Proxy vs CGLIB Proxy:**
- **JDK Proxy**: Interface-based, uses `java.lang.reflect.Proxy`
- **CGLIB Proxy**: Subclass-based, bytecode generation at runtime
- Spring Boot defaults to CGLIB proxies (`spring.aop.proxy-target-class=true`)

---

## Request Processing Pipeline

### Q8: Complete HTTP Request Flow in Spring Boot (Servlet Stack)

```
Client Request (HTTP)
    │
    ▼
┌─────────────────────────────────────────────────┐
│  EMBEDDED TOMCAT / JETTY / UNDERTOW              │
│  ├── Connector (NIO) receives connection         │
│  ├── Protocol (HTTP/1.1, HTTP/2)                 │
│  └── Assigns thread from thread pool             │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────┐
│  SERVLET FILTER CHAIN                            │
│  ├── CharacterEncodingFilter                     │
│  ├── HiddenHttpMethodFilter                      │
│  ├── SecurityFilterChain (Spring Security)       │
│  │   ├── SecurityContextPersistenceFilter        │
│  │   ├── UsernamePasswordAuthenticationFilter    │
│  │   ├── ExceptionTranslationFilter              │
│  │   └── FilterSecurityInterceptor               │
│  ├── CorsFilter                                  │
│  └── Custom Filters                              │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────┐
│  DISPATCHER SERVLET                              │
│  ├── 1. getHandler() → HandlerMapping            │
│  │   ├── RequestMappingHandlerMapping            │
│  │   ├── BeanNameUrlHandlerMapping               │
│  │   └── RouterFunctionMapping                   │
│  │                                               │
│  ├── 2. getHandlerAdapter()                      │
│  │   └── RequestMappingHandlerAdapter            │
│  │                                               │
│  ├── 3. applyPreHandle() → HandlerInterceptors   │
│  │   ├── interceptor1.preHandle()                │
│  │   └── interceptor2.preHandle()                │
│  │                                               │
│  ├── 4. handle() → Invoke Controller Method      │
│  │   ├── Argument Resolution                     │
│  │   │   ├── @RequestBody → HttpMessageConverter │
│  │   │   ├── @PathVariable → PathVariableResolver│
│  │   │   ├── @RequestParam → RequestParamResolver│
│  │   │   └── @Valid → Validator                  │
│  │   ├── Method Invocation (via reflection)      │
│  │   └── Return Value Handling                   │
│  │       ├── @ResponseBody → HttpMessageConverter│
│  │       └── ModelAndView → ViewResolver         │
│  │                                               │
│  ├── 5. applyPostHandle() → HandlerInterceptors  │
│  │   ├── interceptor2.postHandle()               │
│  │   └── interceptor1.postHandle()               │
│  │                                               │
│  ├── 6. processDispatchResult()                  │
│  │   └── Exception handling if needed            │
│  │       └── @ExceptionHandler / @ControllerAdvice│
│  │                                               │
│  └── 7. afterCompletion() → HandlerInterceptors  │
└─────────────────────────────────────────────────┘
    │
    ▼
Response sent back to client
```

### Q9: How does `@RequestBody` deserialization work internally?

**Answer:**

```java
// Flow: @RequestBody → RequestResponseBodyMethodProcessor → HttpMessageConverter

// 1. RequestResponseBodyMethodProcessor.resolveArgument()
public Object resolveArgument(MethodParameter parameter, ...) {
    // 2. Read the HTTP message body
    Object arg = readWithMessageConverters(webRequest, parameter, paramType);
    
    // 3. Validate if @Valid is present
    if (parameter.hasParameterAnnotation(Valid.class)) {
        validator.validate(arg);
    }
    
    return arg;
}

// 4. Inside readWithMessageConverters:
for (HttpMessageConverter<?> converter : this.messageConverters) {
    if (converter.canRead(targetClass, contentType)) {
        // For JSON: MappingJackson2HttpMessageConverter
        return converter.read(targetClass, inputMessage);
    }
}
```

**Jackson Deserialization Chain:**
```
HTTP Body (JSON bytes)
  → MappingJackson2HttpMessageConverter.read()
    → ObjectMapper.readValue()
      → JsonParser (tokenizes JSON)
        → BeanDeserializer (constructs object)
          → SettableBeanProperty.deserializeAndSet() (for each field)
            → Final POJO
```

---

## Embedded Server Architecture

### Q10: How does the embedded Tomcat work in Spring Boot?

**Answer:**

```java
// When onRefresh() is called during context refresh:
// ServletWebServerApplicationContext.onRefresh()
protected void onRefresh() {
    createWebServer();
}

private void createWebServer() {
    // 1. Get the factory
    ServletWebServerFactory factory = getWebServerFactory();
    // Returns TomcatServletWebServerFactory / JettyServletWebServerFactory / UndertowServletWebServerFactory
    
    // 2. Create the web server
    this.webServer = factory.getWebServer(getSelfInitializer());
    // This creates Tomcat instance, configures connectors, etc.
}
```

**Tomcat Architecture in Spring Boot:**

```
TomcatWebServer
  └── Tomcat (org.apache.catalina.startup.Tomcat)
        ├── Server
        │   └── Service
        │       ├── Connector (HTTP/1.1, port 8080)
        │       │   ├── ProtocolHandler (Http11NioProtocol)
        │       │   │   ├── NioEndpoint
        │       │   │   │   ├── Acceptor thread (accepts connections)
        │       │   │   │   ├── Poller thread (NIO selector, monitors ready channels)
        │       │   │   │   └── Worker threads (thread pool, processes requests)
        │       │   │   └── ConnectionHandler
        │       │   └── Adapter (CoyoteAdapter)
        │       │
        │       └── Engine
        │           └── Host (localhost)
        │               └── Context (/ application)
        │                   └── Wrapper (DispatcherServlet)
        └── Connector Configuration
            ├── maxThreads (default: 200)
            ├── minSpareThreads (default: 10)
            ├── maxConnections (default: 8192)
            ├── acceptCount (default: 100)
            └── connectionTimeout (default: 20000ms)
```

### Q11: Explain Tomcat's NIO Thread Model

```
                    ┌──────────────┐
                    │   Acceptor   │  (1 thread)
                    │   Thread     │  Accepts new TCP connections
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   Poller     │  (1-2 threads)
                    │   Thread     │  NIO Selector - monitors socket channels
                    └──────┬───────┘  for read/write readiness
                           │
                           ▼
              ┌────────────────────────┐
              │    Worker Thread Pool   │  (10-200 threads)
              │  ┌─────┐ ┌─────┐      │
              │  │ T-1 │ │ T-2 │ ...  │  Processes HTTP requests
              │  └─────┘ └─────┘      │  (blocking per request)
              └────────────────────────┘
```

**Key Configuration Properties:**

```yaml
server:
  tomcat:
    threads:
      max: 200          # Maximum worker threads
      min-spare: 10     # Minimum idle threads
    max-connections: 8192  # Max simultaneous connections
    accept-count: 100      # Queue size when all threads busy
    connection-timeout: 20000  # Connection timeout in ms
  port: 8080
```

---

## Dependency Injection Internals

### Q12: How does `@Autowired` work internally?

**Answer:**

```java
// AutowiredAnnotationBeanPostProcessor handles @Autowired
public class AutowiredAnnotationBeanPostProcessor implements BeanPostProcessor {
    
    // During bean creation, BEFORE initialization:
    @Override
    public PropertyValues postProcessProperties(PropertyValues pvs, Object bean, String beanName) {
        // 1. Find injection metadata (cached after first call)
        InjectionMetadata metadata = findAutowiringMetadata(beanName, bean.getClass());
        
        // 2. Inject dependencies
        metadata.inject(bean, beanName, pvs);
        return pvs;
    }
}

// InjectionMetadata.inject() for each field/method:
protected void inject(Object bean, String beanName, PropertyValues pvs) {
    Field field = (Field) this.member;
    Object value;
    
    // Resolve the dependency from BeanFactory
    value = beanFactory.resolveDependency(descriptor, beanName, autowiredBeanNames, typeConverter);
    
    // Set via reflection
    field.setAccessible(true);
    field.set(bean, value);
}
```

**Resolution Strategy:**
```
@Autowired resolution:
1. By Type (primary strategy)
2. If multiple candidates:
   a. Check @Primary
   b. Check @Priority (javax.annotation.Priority)
   c. Match by name (field name / parameter name matches bean name)
   d. If still ambiguous → NoUniqueBeanDefinitionException
```

### Q13: What's the difference between Constructor, Setter, and Field injection?

| Aspect | Constructor | Setter | Field |
|--------|------------|--------|-------|
| Immutability | Yes (final fields) | No | No |
| Required deps | Enforced | Optional (with required=false) | Optional |
| Circular deps | Fails fast | Allowed | Allowed |
| Testability | Easy (plain constructor) | Easy (setter methods) | Hard (needs reflection) |
| Best practice | Recommended | For optional deps | Avoid |

**Why Constructor Injection is preferred:**
```java
@Service
public class OrderService {
    private final PaymentService paymentService;  // immutable
    private final InventoryService inventoryService;  // immutable
    
    // Single constructor - @Autowired not even needed (Spring 4.3+)
    public OrderService(PaymentService paymentService, InventoryService inventoryService) {
        this.paymentService = paymentService;
        this.inventoryService = inventoryService;
    }
}
```

---

## Spring Boot Starter Mechanism

### Q14: How do Spring Boot Starters work?

**Answer:**

A starter is a dependency aggregator + auto-configuration provider.

```
spring-boot-starter-web
  ├── spring-boot-starter (core)
  │   ├── spring-boot
  │   ├── spring-boot-autoconfigure
  │   └── spring-boot-starter-logging
  ├── spring-web
  ├── spring-webmvc
  ├── spring-boot-starter-tomcat
  │   └── tomcat-embed-core
  └── spring-boot-starter-json
      └── jackson-databind
```

**Creating a custom starter:**

```
my-custom-starter/
  ├── pom.xml (dependencies only, no code)
  └── my-custom-starter-autoconfigure/
      ├── src/main/java/
      │   └── com/example/autoconfigure/
      │       ├── MyServiceAutoConfiguration.java
      │       └── MyServiceProperties.java
      └── src/main/resources/
          └── META-INF/
              └── spring/
                  └── org.springframework.boot.autoconfigure.AutoConfiguration.imports
```

```java
@AutoConfiguration
@ConditionalOnClass(MyService.class)
@EnableConfigurationProperties(MyServiceProperties.class)
public class MyServiceAutoConfiguration {
    
    @Bean
    @ConditionalOnMissingBean
    public MyService myService(MyServiceProperties properties) {
        return new MyService(properties.getUrl(), properties.getTimeout());
    }
}
```

---

## Actuator Internals

### Q15: How does Spring Boot Actuator work internally?

**Answer:**

```
Actuator Architecture:
  ├── Endpoints (data providers)
  │   ├── HealthEndpoint
  │   ├── MetricsEndpoint
  │   ├── InfoEndpoint
  │   └── Custom endpoints (@Endpoint)
  │
  ├── Web Exposure (HTTP layer)
  │   ├── EndpointMapping (/actuator/*)
  │   ├── WebEndpointDiscoverer (finds all web-exposed endpoints)
  │   └── EndpointWebMvcHandlerMapping (registers routes)
  │
  └── Infrastructure
      ├── HealthIndicators (DB, Redis, Disk, Custom)
      ├── MeterRegistry (Micrometer - metrics collection)
      └── AuditEventRepository
```

**Health Check Internals:**

```java
// HealthEndpoint aggregates all HealthIndicators
@Endpoint(id = "health")
public class HealthEndpoint {
    
    @ReadOperation
    public HealthComponent health() {
        // Calls all registered HealthIndicators
        // Aggregates results using StatusAggregator
        // Returns composite health status
    }
}

// Custom HealthIndicator
@Component
public class DatabaseHealthIndicator implements HealthIndicator {
    @Override
    public Health health() {
        try {
            // Check database connectivity
            jdbcTemplate.queryForObject("SELECT 1", Integer.class);
            return Health.up()
                .withDetail("database", "PostgreSQL")
                .withDetail("latency", "5ms")
                .build();
        } catch (Exception e) {
            return Health.down(e).build();
        }
    }
}
```

---

## Class Loading and Context Hierarchy

### Q16: How does Spring Boot handle class loading?

**Answer:**

```
Spring Boot Executable JAR (Fat JAR):
  ├── BOOT-INF/
  │   ├── classes/        (your application classes)
  │   └── lib/            (all dependency JARs)
  ├── META-INF/
  │   └── MANIFEST.MF    (Main-Class: JarLauncher)
  └── org/springframework/boot/loader/
      ├── JarLauncher.class
      ├── LaunchedURLClassLoader.class
      └── jar/
          └── JarFile.class (reads nested JARs)

ClassLoader Hierarchy:
  System ClassLoader (JDK classes)
    └── LaunchedURLClassLoader (Spring Boot's custom)
          ├── BOOT-INF/classes/
          └── BOOT-INF/lib/*.jar (loaded as nested URLs)
```

**Why nested JARs?**
- Standard JAR specification doesn't support JAR-within-JAR
- Spring Boot's `LaunchedURLClassLoader` handles this with custom `JarFile` implementation
- Allows fat JAR execution without extraction

### Q17: Explain the ApplicationContext hierarchy in Spring Boot

```
For a typical web application:

Root ApplicationContext (parent)
  ├── Service beans
  ├── Repository beans
  ├── Infrastructure beans
  └── DispatcherServlet ApplicationContext (child)
      ├── Controllers
      ├── ViewResolvers
      ├── HandlerMappings
      └── Can access parent beans (but not vice versa)

In Spring Boot (simplified - single context by default):
AnnotationConfigServletWebServerApplicationContext
  ├── All beans (no parent-child split by default)
  ├── Embedded server created here
  └── DispatcherServlet registered as a bean
```

---

## Configuration Processing

### Q18: How does `@ConfigurationProperties` binding work?

**Answer:**

```java
// 1. Properties are loaded from multiple sources (PropertySource order):
//    - Command line args
//    - JNDI attributes
//    - System properties
//    - OS environment variables
//    - application-{profile}.yml
//    - application.yml
//    - @PropertySource annotations
//    - Default properties

// 2. Binding happens via ConfigurationPropertiesBindingPostProcessor

@ConfigurationProperties(prefix = "app.datasource")
public class DataSourceProperties {
    private String url;           // binds: app.datasource.url
    private String username;      // binds: app.datasource.username
    private Duration timeout;     // binds: app.datasource.timeout (supports "5s", "100ms")
    private DataSize maxSize;     // binds: app.datasource.max-size (supports "10MB")
    private List<String> hosts;   // binds: app.datasource.hosts[0], hosts[1]
    private Map<String, String> props; // binds: app.datasource.props.key=value
}
```

**Relaxed Binding Rules:**
```
Property: app.datasource.max-connections
Matches:
  - app.datasource.max-connections (kebab-case - RECOMMENDED)
  - app.datasource.maxConnections (camelCase)
  - app.datasource.max_connections (underscore)
  - APP_DATASOURCE_MAX_CONNECTIONS (uppercase with underscore - env vars)
```

---

## Profile Mechanism

### Q19: How do Spring Profiles work internally?

**Answer:**

```java
// Profile activation chain:
// 1. Environment.setActiveProfiles() or spring.profiles.active property
// 2. During component scanning, @Profile is evaluated:

@Profile("production")
@Configuration
public class ProductionConfig {
    // Only loaded when "production" profile is active
}

// Internally, ProfileCondition evaluates:
class ProfileCondition implements Condition {
    @Override
    public boolean matches(ConditionContext context, AnnotatedTypeMetadata metadata) {
        MultiValueMap<String, Object> attrs = metadata.getAllAnnotationAttributes(Profile.class.getName());
        if (attrs != null) {
            for (Object value : attrs.get("value")) {
                if (context.getEnvironment().acceptsProfiles(Profiles.of((String[]) value))) {
                    return true;
                }
            }
            return false;
        }
        return true;
    }
}
```

**Profile-specific configuration loading order:**
```
1. application.yml (always loaded)
2. application-{profile}.yml (overrides base)
3. application-{profile}.yml from config/ directory
4. External config locations
```

---

## Event System

### Q20: How does Spring's Event system work internally?

**Answer:**

```java
// Publisher
@Service
public class OrderService {
    @Autowired
    private ApplicationEventPublisher publisher;
    
    public void createOrder(Order order) {
        // ... business logic
        publisher.publishEvent(new OrderCreatedEvent(this, order));
    }
}

// Listener
@Component
public class NotificationListener {
    
    @EventListener
    public void handleOrderCreated(OrderCreatedEvent event) {
        // Handle synchronously by default (same thread)
    }
    
    @Async
    @EventListener
    public void handleOrderCreatedAsync(OrderCreatedEvent event) {
        // Handle asynchronously (different thread)
    }
    
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handleAfterCommit(OrderCreatedEvent event) {
        // Only executes after transaction commits
    }
}
```

**Internal Mechanism:**
```
ApplicationEventPublisher.publishEvent()
  └── ApplicationEventMulticaster.multicastEvent()
        ├── Find all matching ApplicationListeners
        ├── For each listener:
        │   ├── If @Async: Submit to TaskExecutor
        │   └── Else: Invoke directly (same thread)
        └── Handle errors (by default, exception propagates)
```

---

## Spring Boot DevTools

### Q21: How does Spring Boot DevTools achieve fast restarts?

**Answer:**

```
DevTools uses TWO ClassLoaders:

Base ClassLoader (never reloaded):
  └── Third-party JARs (Spring Framework, Jackson, etc.)

Restart ClassLoader (thrown away & recreated on file change):
  └── Your application classes

On code change:
1. File system watcher detects change
2. Old Restart ClassLoader is discarded
3. New Restart ClassLoader is created
4. Application classes are reloaded
5. ApplicationContext is refreshed

This is MUCH faster than full JVM restart because:
- Third-party classes stay loaded
- JIT-compiled code for libraries is preserved
- Only your classes (~100s) are reloaded vs all classes (~10000s)
```

---

## Summary of Critical Internal Concepts

| Concept | Key Class | Purpose |
|---------|----------|---------|
| Bootstrap | SpringApplication | Application startup orchestrator |
| Auto-config | AutoConfigurationImportSelector | Loads conditional configurations |
| Bean creation | DefaultListableBeanFactory | Central bean registry and factory |
| DI | AutowiredAnnotationBeanPostProcessor | Handles @Autowired injection |
| AOP | AbstractAutoProxyCreator | Creates proxies for advised beans |
| Request routing | DispatcherServlet | Front controller pattern |
| Embedded server | TomcatServletWebServerFactory | Creates and configures Tomcat |
| Config binding | ConfigurationPropertiesBindingPostProcessor | Binds properties to POJOs |
| Actuator | EndpointDiscoverer | Discovers and exposes endpoints |
| Events | ApplicationEventMulticaster | Event routing and delivery |
