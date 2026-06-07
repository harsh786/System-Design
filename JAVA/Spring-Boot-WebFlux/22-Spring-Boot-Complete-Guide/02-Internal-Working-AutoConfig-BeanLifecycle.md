# Spring Boot Internal Working - Complete Guide

## Table of Contents
1. [Application Startup Process](#application-startup-process)
2. [Auto-Configuration Mechanism](#auto-configuration-mechanism)
3. [Component Scanning](#component-scanning)
4. [Bean Lifecycle](#bean-lifecycle)
5. [Dependency Injection Internals](#dependency-injection-internals)
6. [Embedded Server Architecture](#embedded-server-architecture)
7. [Request Processing Pipeline](#request-processing-pipeline)
8. [Spring Boot Starter Mechanism](#spring-boot-starter-mechanism)
9. [ApplicationContext Hierarchy](#applicationcontext-hierarchy)
10. [Properties & Configuration Loading Order](#properties--configuration-loading-order)

---

## Application Startup Process

### What happens when you call `SpringApplication.run()`

```java
@SpringBootApplication
public class MyApp {
    public static void main(String[] args) {
        SpringApplication.run(MyApp.class, args); // Everything starts here
    }
}
```

### Detailed Startup Sequence

```
┌─────────────────────────────────────────────────────────────────┐
│                    SpringApplication.run()                        │
├─────────────────────────────────────────────────────────────────┤
│ 1. Create SpringApplication instance                             │
│    ├── Determine WebApplicationType (SERVLET/REACTIVE/NONE)      │
│    ├── Load ApplicationContextInitializers (from spring.factories)│
│    └── Load ApplicationListeners (from spring.factories)         │
│                                                                   │
│ 2. Run method execution                                          │
│    ├── Create & start StopWatch                                  │
│    ├── Get SpringApplicationRunListeners                         │
│    ├── Publish ApplicationStartingEvent                          │
│    ├── Prepare Environment                                       │
│    │   ├── Create ConfigurableEnvironment                        │
│    │   ├── Configure property sources                            │
│    │   ├── Publish ApplicationEnvironmentPreparedEvent           │
│    │   └── Bind spring.main.* properties                         │
│    ├── Print Banner                                              │
│    ├── Create ApplicationContext                                 │
│    │   └── AnnotationConfigServletWebServerApplicationContext    │
│    ├── Prepare Context                                           │
│    │   ├── Set Environment                                       │
│    │   ├── Apply ApplicationContextInitializers                  │
│    │   ├── Publish ApplicationContextInitializedEvent            │
│    │   ├── Register main class as bean definition                │
│    │   └── Publish ApplicationPreparedEvent                      │
│    ├── Refresh Context (THE BIG ONE)                             │
│    │   ├── Prepare BeanFactory                                   │
│    │   ├── Invoke BeanFactoryPostProcessors                      │
│    │   │   ├── ConfigurationClassPostProcessor                   │
│    │   │   │   ├── Parse @Configuration classes                  │
│    │   │   │   ├── Process @ComponentScan                        │
│    │   │   │   ├── Process @Import                               │
│    │   │   │   ├── Process @Bean methods                         │
│    │   │   │   └── Process @ImportResource                       │
│    │   │   └── PropertySourcesPlaceholderConfigurer              │
│    │   ├── Register BeanPostProcessors                           │
│    │   ├── Initialize MessageSource                              │
│    │   ├── Initialize ApplicationEventMulticaster                │
│    │   ├── onRefresh() → Start embedded web server               │
│    │   ├── Register Listeners                                    │
│    │   ├── Finalize BeanFactory (instantiate singletons)         │
│    │   └── Publish ContextRefreshedEvent                         │
│    ├── Publish ApplicationStartedEvent                           │
│    ├── Call ApplicationRunners & CommandLineRunners               │
│    └── Publish ApplicationReadyEvent                             │
└─────────────────────────────────────────────────────────────────┘
```

### SpringApplication Internal Code Flow

```java
// Simplified internal flow
public class SpringApplication {
    
    public ConfigurableApplicationContext run(String... args) {
        // 1. Determine app type
        this.webApplicationType = WebApplicationType.deduceFromClasspath();
        // Checks: DispatcherServlet → SERVLET, DispatcherHandler → REACTIVE, else NONE
        
        // 2. Load spring.factories
        this.initializers = loadSpringFactories(ApplicationContextInitializer.class);
        this.listeners = loadSpringFactories(ApplicationListener.class);
        
        // 3. Detect main application class
        this.mainApplicationClass = deduceMainApplicationClass();
        
        // 4. Prepare environment
        ConfigurableEnvironment environment = prepareEnvironment(listeners, args);
        
        // 5. Create context
        ConfigurableApplicationContext context = createApplicationContext();
        // For SERVLET: AnnotationConfigServletWebServerApplicationContext
        // For REACTIVE: AnnotationConfigReactiveWebServerApplicationContext
        
        // 6. Refresh context - THIS IS WHERE EVERYTHING HAPPENS
        refreshContext(context);
        
        // 7. Call runners
        callRunners(context, args);
        
        return context;
    }
}
```

---

## Auto-Configuration Mechanism

### How Auto-Configuration Works

```
┌──────────────────────────────────────────────────────────┐
│               AUTO-CONFIGURATION FLOW                      │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  1. @EnableAutoConfiguration triggers                     │
│     AutoConfigurationImportSelector                       │
│           │                                               │
│           ▼                                               │
│  2. Reads META-INF/spring/                               │
│     org.springframework.boot.autoconfigure.              │
│     AutoConfiguration.imports                             │
│           │                                               │
│           ▼                                               │
│  3. Loads all listed auto-configuration classes           │
│     (200+ classes in spring-boot-autoconfigure)           │
│           │                                               │
│           ▼                                               │
│  4. Each class has @Conditional* annotations              │
│     - @ConditionalOnClass                                │
│     - @ConditionalOnMissingBean                          │
│     - @ConditionalOnProperty                             │
│           │                                               │
│           ▼                                               │
│  5. Spring evaluates conditions                           │
│     - Only matching configs are applied                   │
│     - User-defined beans take priority                    │
│           │                                               │
│           ▼                                               │
│  6. Auto-configured beans are created                     │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### Example: DataSource Auto-Configuration

```java
// spring-boot-autoconfigure module
@AutoConfiguration(before = SqlInitializationAutoConfiguration.class)
@ConditionalOnClass({DataSource.class, EmbeddedDatabaseType.class})
@ConditionalOnMissingBean(type = "io.r2dbc.spi.ConnectionFactory")
@EnableConfigurationProperties(DataSourceProperties.class)
@Import({
    DataSourcePoolMetadataProvidersConfiguration.class,
    DataSourceCheckpointRestoreConfiguration.class
})
public class DataSourceAutoConfiguration {
    
    @Configuration(proxyBeanMethods = false)
    @Conditional(PooledDataSourceCondition.class)
    @ConditionalOnMissingBean({DataSource.class, XADataSource.class})
    @Import({
        DataSourceConfiguration.Hikari.class,  // Default
        DataSourceConfiguration.Tomcat.class,
        DataSourceConfiguration.Dbcp2.class,
        DataSourceConfiguration.OracleUcp.class
    })
    protected static class PooledDataSourceConfiguration { }
}

// What this means:
// 1. Only activates if DataSource class is on classpath
// 2. Only if no R2DBC ConnectionFactory exists
// 3. Only if user hasn't defined their own DataSource bean
// 4. Prefers HikariCP (checks classpath order)
```

### Writing Custom Auto-Configuration

```java
// 1. Create the auto-configuration class
@AutoConfiguration
@ConditionalOnClass(MyLibrary.class)
@ConditionalOnProperty(prefix = "mylib", name = "enabled", havingValue = "true", matchIfMissing = true)
@EnableConfigurationProperties(MyLibProperties.class)
public class MyLibAutoConfiguration {
    
    @Bean
    @ConditionalOnMissingBean
    public MyLibClient myLibClient(MyLibProperties properties) {
        return new MyLibClient(properties.getApiKey(), properties.getBaseUrl());
    }
}

// 2. Register in META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports
// com.example.mylib.MyLibAutoConfiguration

// 3. Properties class
@ConfigurationProperties(prefix = "mylib")
public class MyLibProperties {
    private String apiKey;
    private String baseUrl = "https://api.mylib.com";
    private boolean enabled = true;
    // getters/setters
}
```

### Debugging Auto-Configuration

```yaml
# application.yml
debug: true  # Prints CONDITIONS EVALUATION REPORT at startup

# Or use actuator
management:
  endpoints:
    web:
      exposure:
        include: conditions
```

```
============================
CONDITIONS EVALUATION REPORT
============================

Positive matches:
-----------------
   DataSourceAutoConfiguration matched:
      - @ConditionalOnClass found required classes 'javax.sql.DataSource'

Negative matches:
-----------------
   MongoAutoConfiguration:
      Did not match:
         - @ConditionalOnClass did not find required class 'com.mongodb.client.MongoClient'
```

---

## Component Scanning

### How Component Scanning Works

```java
@SpringBootApplication  // Scans from THIS package and all sub-packages
public class MyApp { }

// Package structure:
// com.example.myapp          ← @SpringBootApplication here
// com.example.myapp.service  ← Scanned ✓
// com.example.myapp.repo     ← Scanned ✓
// com.example.other          ← NOT scanned ✗
```

### Scanning Process

```
┌─────────────────────────────────────────────────────┐
│              COMPONENT SCANNING                       │
├─────────────────────────────────────────────────────┤
│                                                      │
│  1. ClassPathBeanDefinitionScanner starts            │
│           │                                          │
│           ▼                                          │
│  2. Scans classpath for .class files                 │
│     in base packages                                 │
│           │                                          │
│           ▼                                          │
│  3. Uses ASM (not reflection) to read                │
│     class metadata without loading class             │
│           │                                          │
│           ▼                                          │
│  4. Applies include/exclude filters                  │
│     Default includes: @Component and its             │
│     meta-annotations (@Service, @Repository, etc.)   │
│           │                                          │
│           ▼                                          │
│  5. Creates BeanDefinition for each match            │
│           │                                          │
│           ▼                                          │
│  6. Registers in BeanDefinitionRegistry              │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Custom Component Scanning

```java
@Configuration
@ComponentScan(
    basePackages = {"com.example.service", "com.example.repository"},
    includeFilters = @ComponentScan.Filter(
        type = FilterType.ANNOTATION, 
        classes = CustomAnnotation.class
    ),
    excludeFilters = @ComponentScan.Filter(
        type = FilterType.REGEX, 
        pattern = ".*Test.*"
    )
)
public class ScanConfig { }
```

---

## Bean Lifecycle

### Complete Bean Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                    BEAN LIFECYCLE                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─── INSTANTIATION PHASE ───┐                              │
│  │                            │                              │
│  │  1. BeanDefinition read    │                              │
│  │  2. Constructor called     │                              │
│  │  3. Instance created       │                              │
│  └────────────┬───────────────┘                              │
│               │                                              │
│  ┌─── POPULATION PHASE ──────┐                              │
│  │               │            │                              │
│  │  4. @Autowired fields set  │                              │
│  │  5. @Value properties set  │                              │
│  │  6. Setter injection       │                              │
│  └────────────┬───────────────┘                              │
│               │                                              │
│  ┌─── INITIALIZATION PHASE ──┐                              │
│  │               │            │                              │
│  │  7. BeanNameAware          │                              │
│  │     .setBeanName()         │                              │
│  │  8. BeanFactoryAware       │                              │
│  │     .setBeanFactory()      │                              │
│  │  9. ApplicationContextAware│                              │
│  │     .setApplicationContext()│                             │
│  │  10. BeanPostProcessor     │                              │
│  │      .postProcessBefore()  │                              │
│  │  11. @PostConstruct        │                              │
│  │  12. InitializingBean      │                              │
│  │      .afterPropertiesSet() │                              │
│  │  13. Custom init-method    │                              │
│  │  14. BeanPostProcessor     │                              │
│  │      .postProcessAfter()   │  ← AOP proxies created here │
│  └────────────┬───────────────┘                              │
│               │                                              │
│  ┌─── READY FOR USE ─────────┐                              │
│  │               │            │                              │
│  │  Bean is fully initialized │                              │
│  │  and can serve requests    │                              │
│  └────────────┬───────────────┘                              │
│               │                                              │
│  ┌─── DESTRUCTION PHASE ─────┐                              │
│  │               │            │                              │
│  │  15. @PreDestroy           │                              │
│  │  16. DisposableBean        │                              │
│  │      .destroy()            │                              │
│  │  17. Custom destroy-method │                              │
│  └────────────────────────────┘                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Lifecycle Code Example

```java
@Component
public class MyBean implements BeanNameAware, BeanFactoryAware, 
                               ApplicationContextAware, InitializingBean, 
                               DisposableBean {
    
    private String beanName;
    
    // Constructor - Step 2
    public MyBean() {
        System.out.println("1. Constructor called");
    }
    
    // Setter injection - Step 4-6
    @Autowired
    public void setDependency(SomeDependency dep) {
        System.out.println("2. Dependencies injected");
    }
    
    // Aware interfaces - Steps 7-9
    @Override
    public void setBeanName(String name) {
        this.beanName = name;
        System.out.println("3. BeanNameAware: " + name);
    }
    
    @Override
    public void setBeanFactory(BeanFactory factory) {
        System.out.println("4. BeanFactoryAware");
    }
    
    @Override
    public void setApplicationContext(ApplicationContext ctx) {
        System.out.println("5. ApplicationContextAware");
    }
    
    // Initialization - Steps 11-12
    @PostConstruct
    public void postConstruct() {
        System.out.println("6. @PostConstruct");
    }
    
    @Override
    public void afterPropertiesSet() {
        System.out.println("7. InitializingBean.afterPropertiesSet()");
    }
    
    // Destruction - Steps 15-16
    @PreDestroy
    public void preDestroy() {
        System.out.println("8. @PreDestroy");
    }
    
    @Override
    public void destroy() {
        System.out.println("9. DisposableBean.destroy()");
    }
}
```

### BeanPostProcessor - The Extension Point

```java
@Component
public class CustomBeanPostProcessor implements BeanPostProcessor {
    
    @Override
    public Object postProcessBeforeInitialization(Object bean, String beanName) {
        // Called BEFORE @PostConstruct
        if (bean instanceof MyService) {
            System.out.println("Before init: " + beanName);
        }
        return bean;
    }
    
    @Override
    public Object postProcessAfterInitialization(Object bean, String beanName) {
        // Called AFTER @PostConstruct
        // THIS is where AOP proxies are created!
        if (bean.getClass().isAnnotationPresent(Monitored.class)) {
            return createMonitoringProxy(bean);
        }
        return bean;
    }
}
```

### Key BeanPostProcessors in Spring Boot

| BeanPostProcessor | Purpose |
|---|---|
| `AutowiredAnnotationBeanPostProcessor` | Handles `@Autowired`, `@Value` |
| `CommonAnnotationBeanPostProcessor` | Handles `@PostConstruct`, `@PreDestroy`, `@Resource` |
| `AnnotationAwareAspectJAutoProxyCreator` | Creates AOP proxies |
| `AsyncAnnotationBeanPostProcessor` | Handles `@Async` |
| `ScheduledAnnotationBeanPostProcessor` | Handles `@Scheduled` |
| `PersistenceExceptionTranslationPostProcessor` | `@Repository` exception translation |

---

## Dependency Injection Internals

### How Spring Resolves Dependencies

```
┌──────────────────────────────────────────────────────────────┐
│         DEPENDENCY RESOLUTION ALGORITHM                        │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  When injecting a dependency of Type T:                       │
│                                                               │
│  1. Find all beans of Type T in the context                   │
│     ├── If 0 found → NoSuchBeanDefinitionException            │
│     ├── If 1 found → Inject it                                │
│     └── If N found → Disambiguation:                          │
│         ├── Check @Primary → Use primary bean                 │
│         ├── Check @Qualifier → Match by qualifier             │
│         ├── Match by parameter name → Bean name match         │
│         └── If still ambiguous → NoUniqueBeanDefinitionExcept.│
│                                                               │
│  Special cases:                                               │
│  - List<T> → Injects ALL beans of type T                      │
│  - Optional<T> → Wraps single bean or empty                   │
│  - Map<String, T> → Bean name → bean instance                 │
│  - ObjectProvider<T> → Lazy resolution                        │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Circular Dependency Resolution

```java
// Circular dependency:
@Service
public class ServiceA {
    @Autowired
    private ServiceB serviceB; // ServiceB needs ServiceA too!
}

@Service
public class ServiceB {
    @Autowired
    private ServiceA serviceA; // Circular!
}
```

**How Spring resolves (for singleton field/setter injection):**
1. Spring starts creating ServiceA
2. Exposes an "early reference" (partially constructed) in the "third-level cache"
3. Starts creating ServiceB
4. ServiceB needs ServiceA → gets the early reference
5. ServiceB completes initialization
6. ServiceA gets fully initialized ServiceB

**Three-Level Cache:**
```
singletonObjects          (1st cache) → Fully initialized beans
earlySingletonObjects     (2nd cache) → Early references (proxies if needed)
singletonFactories        (3rd cache) → ObjectFactory to create early reference
```

**Circular dependencies FAIL with constructor injection:**
```java
// This WILL fail - no way to resolve
@Service
public class ServiceA {
    public ServiceA(ServiceB serviceB) { } // Needs B to construct
}

@Service
public class ServiceB {
    public ServiceB(ServiceA serviceA) { } // Needs A to construct → DEADLOCK
}

// Solution: Use @Lazy
@Service
public class ServiceA {
    public ServiceA(@Lazy ServiceB serviceB) { } // Injects proxy, resolves later
}
```

---

## Embedded Server Architecture

### How Embedded Tomcat Works

```
┌────────────────────────────────────────────────────────────┐
│               EMBEDDED TOMCAT ARCHITECTURE                   │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Spring Boot Application (Single JAR)                       │
│  ┌─────────────────────────────────────────────────┐       │
│  │                                                  │       │
│  │  ┌─────────────────────────────────────┐        │       │
│  │  │         Embedded Tomcat              │        │       │
│  │  │  ┌───────────────────────────────┐  │        │       │
│  │  │  │     Connector (port 8080)     │  │        │       │
│  │  │  │  ┌────────────────────────┐   │  │        │       │
│  │  │  │  │  NIO Endpoint          │   │  │        │       │
│  │  │  │  │  (Acceptor + Poller)   │   │  │        │       │
│  │  │  │  └────────────────────────┘   │  │        │       │
│  │  │  └───────────────────────────────┘  │        │       │
│  │  │  ┌───────────────────────────────┐  │        │       │
│  │  │  │     Engine (Catalina)         │  │        │       │
│  │  │  │  ┌────────────────────────┐   │  │        │       │
│  │  │  │  │   Host (localhost)     │   │  │        │       │
│  │  │  │  │  ┌─────────────────┐   │   │  │        │       │
│  │  │  │  │  │  Context (/)    │   │   │  │        │       │
│  │  │  │  │  │                 │   │   │  │        │       │
│  │  │  │  │  │ DispatcherServlet│  │   │  │        │       │
│  │  │  │  │  └─────────────────┘   │   │  │        │       │
│  │  │  │  └────────────────────────┘   │  │        │       │
│  │  │  └───────────────────────────────┘  │        │       │
│  │  └─────────────────────────────────────┘        │       │
│  │                                                  │       │
│  │  Spring ApplicationContext                       │       │
│  │  ┌──────────────────────────────────────┐       │       │
│  │  │ Controllers, Services, Repositories  │       │       │
│  │  └──────────────────────────────────────┘       │       │
│  └─────────────────────────────────────────────────┘       │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

### Server Auto-Configuration

```java
// Spring Boot automatically configures based on classpath:
// - spring-boot-starter-web → Embedded Tomcat (default)
// - spring-boot-starter-webflux → Embedded Netty (default)

// To switch servers:
// Exclude Tomcat, add Jetty:
// implementation('org.springframework.boot:spring-boot-starter-web') {
//     exclude group: 'org.springframework.boot', module: 'spring-boot-starter-tomcat'
// }
// implementation 'org.springframework.boot:spring-boot-starter-jetty'
```

### Server Configuration

```yaml
server:
  port: 8080
  tomcat:
    threads:
      max: 200          # Max worker threads
      min-spare: 10     # Min idle threads
    max-connections: 8192  # Max connections
    accept-count: 100      # Queue when all threads busy
    connection-timeout: 20000  # 20 seconds
    max-http-form-post-size: 2MB
  compression:
    enabled: true
    min-response-size: 1024
    mime-types: application/json,text/html,text/plain
  shutdown: graceful     # Wait for active requests to complete
  
spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s  # Max wait during graceful shutdown
```

---

## Request Processing Pipeline

### DispatcherServlet Flow

```
┌─────────────────────────────────────────────────────────────────┐
│              HTTP REQUEST PROCESSING PIPELINE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  HTTP Request → Tomcat NIO Connector                             │
│       │                                                          │
│       ▼                                                          │
│  Filter Chain (ordered)                                          │
│  ├── CharacterEncodingFilter                                     │
│  ├── CorsFilter                                                  │
│  ├── SecurityFilterChain (15+ filters)                           │
│  │   ├── SecurityContextPersistenceFilter                        │
│  │   ├── UsernamePasswordAuthenticationFilter                    │
│  │   ├── BearerTokenAuthenticationFilter                         │
│  │   ├── ExceptionTranslationFilter                              │
│  │   └── FilterSecurityInterceptor                               │
│  └── Other custom filters                                        │
│       │                                                          │
│       ▼                                                          │
│  DispatcherServlet.doDispatch()                                  │
│       │                                                          │
│       ├── 1. HandlerMapping                                      │
│       │      Finds which controller method handles this URL      │
│       │      RequestMappingHandlerMapping (annotation-based)     │
│       │                                                          │
│       ├── 2. HandlerAdapter                                      │
│       │      RequestMappingHandlerAdapter                        │
│       │                                                          │
│       ├── 3. HandlerInterceptor.preHandle()                      │
│       │      Custom interceptors execute                         │
│       │                                                          │
│       ├── 4. Argument Resolution                                 │
│       │      ├── @PathVariable → PathVariableMethodArgumentResolver│
│       │      ├── @RequestBody → RequestResponseBodyMethodProcessor│
│       │      ├── @RequestParam → RequestParamMethodArgumentResolver│
│       │      └── @Valid → Triggers Bean Validation               │
│       │                                                          │
│       ├── 5. Controller Method Invoked                           │
│       │      Business logic executes                             │
│       │                                                          │
│       ├── 6. Return Value Handling                               │
│       │      ├── ResponseEntity → Direct response                │
│       │      ├── @ResponseBody → HttpMessageConverter            │
│       │      │   └── MappingJackson2HttpMessageConverter         │
│       │      └── String → ViewResolver                           │
│       │                                                          │
│       ├── 7. HandlerInterceptor.postHandle()                     │
│       │                                                          │
│       └── 8. HandlerInterceptor.afterCompletion()                │
│                                                                   │
│  HTTP Response ← Written to client                               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Content Negotiation

```java
// How Spring determines response format:
// 1. URL suffix (deprecated): /api/users.json
// 2. Request parameter: /api/users?format=json
// 3. Accept header: Accept: application/json (PREFERRED)

// Spring selects HttpMessageConverter based on:
// - Produces attribute on @RequestMapping
// - Accept header from client
// - Available converters on classpath

@GetMapping(value = "/users", produces = {MediaType.APPLICATION_JSON_VALUE, MediaType.APPLICATION_XML_VALUE})
public List<User> getUsers() { ... }
```

---

## Spring Boot Starter Mechanism

### What is a Starter?

A starter is a convenient dependency descriptor - a single dependency that pulls in everything needed for a specific feature.

```
spring-boot-starter-web
├── spring-boot-starter (base)
│   ├── spring-boot
│   ├── spring-boot-autoconfigure
│   ├── spring-boot-starter-logging (Logback)
│   └── jakarta.annotation-api
├── spring-web
├── spring-webmvc
├── spring-boot-starter-json
│   ├── jackson-databind
│   ├── jackson-datatype-jdk8
│   └── jackson-datatype-jsr310
└── spring-boot-starter-tomcat
    ├── tomcat-embed-core
    ├── tomcat-embed-el
    └── tomcat-embed-websocket
```

### Creating a Custom Starter

```
my-custom-starter/
├── my-custom-starter/                    (starter module - just dependencies)
│   └── pom.xml                           (depends on autoconfigure module)
├── my-custom-starter-autoconfigure/      (autoconfigure module)
│   ├── src/main/java/
│   │   └── com/example/
│   │       ├── MyAutoConfiguration.java
│   │       └── MyProperties.java
│   └── src/main/resources/
│       └── META-INF/
│           └── spring/
│               └── org.springframework.boot.autoconfigure.AutoConfiguration.imports
└── pom.xml
```

---

## ApplicationContext Hierarchy

### Context Types

```java
// For Servlet web applications:
AnnotationConfigServletWebServerApplicationContext
    extends ServletWebServerApplicationContext
        extends GenericWebApplicationContext
            extends GenericApplicationContext
                extends AbstractApplicationContext
                    implements ConfigurableApplicationContext

// For Reactive web applications:
AnnotationConfigReactiveWebServerApplicationContext

// For non-web applications:
AnnotationConfigApplicationContext
```

### What ApplicationContext Provides

```
┌────────────────────────────────────────────────┐
│            ApplicationContext                    │
├────────────────────────────────────────────────┤
│                                                 │
│  BeanFactory                                    │
│  ├── Bean creation & management                 │
│  ├── Dependency injection                       │
│  └── Scope management                           │
│                                                 │
│  ResourceLoader                                 │
│  └── Load files from classpath, filesystem      │
│                                                 │
│  ApplicationEventPublisher                      │
│  └── Publish/subscribe events                   │
│                                                 │
│  MessageSource                                  │
│  └── Internationalization (i18n)                │
│                                                 │
│  EnvironmentCapable                             │
│  └── Access properties & profiles               │
│                                                 │
└────────────────────────────────────────────────┘
```

---

## Properties & Configuration Loading Order

### Property Source Priority (highest to lowest)

```
1.  Command-line arguments (--server.port=9090)
2.  SPRING_APPLICATION_JSON (inline JSON in env variable)
3.  ServletConfig init parameters
4.  ServletContext init parameters
5.  JNDI attributes
6.  Java System properties (System.getProperties())
7.  OS environment variables
8.  RandomValuePropertySource (random.*)
9.  Profile-specific application-{profile}.yml OUTSIDE jar
10. Profile-specific application-{profile}.yml INSIDE jar
11. application.yml OUTSIDE jar
12. application.yml INSIDE jar
13. @PropertySource annotations
14. Default properties (SpringApplication.setDefaultProperties)
```

### Configuration File Loading Locations

```
# Spring Boot searches these locations (in order):
1. classpath:/
2. classpath:/config/
3. file:./
4. file:./config/
5. file:./config/*/

# File names (in order):
1. application.properties
2. application.yml
3. application-{profile}.properties
4. application-{profile}.yml
```

### Profile Activation

```yaml
# application.yml
spring:
  profiles:
    active: ${SPRING_PROFILES_ACTIVE:dev}  # From env var or default to dev
    group:
      production:
        - proddb
        - prodmq
        - monitoring

---
# application-dev.yml (separate file or document separator)
spring:
  config:
    activate:
      on-profile: dev
  datasource:
    url: jdbc:h2:mem:devdb

---
spring:
  config:
    activate:
      on-profile: production
  datasource:
    url: jdbc:postgresql://prod-host:5432/mydb
```

---

## Key Internal Classes to Know

| Class | Role |
|-------|------|
| `SpringApplication` | Bootstraps the application |
| `AnnotationConfigServletWebServerApplicationContext` | The main container |
| `ConfigurationClassPostProcessor` | Parses @Configuration, @Bean, @Import |
| `AutoConfigurationImportSelector` | Loads auto-configuration classes |
| `ConditionEvaluator` | Evaluates @Conditional annotations |
| `DefaultListableBeanFactory` | The actual bean container |
| `DispatcherServlet` | Front controller for all requests |
| `RequestMappingHandlerMapping` | Maps URLs to controller methods |
| `RequestMappingHandlerAdapter` | Invokes controller methods |
| `BeanDefinitionReader` | Reads bean definitions from sources |

---

## Startup Performance Optimization

```java
// 1. Lazy initialization (Spring Boot 2.2+)
spring.main.lazy-initialization=true
// Beans created on first access, not at startup
// Faster startup, but first request is slower

// 2. Exclude unnecessary auto-configurations
@SpringBootApplication(exclude = {
    DataSourceAutoConfiguration.class,
    MongoAutoConfiguration.class,
    SecurityAutoConfiguration.class
})

// 3. Use @Indexed for component scanning (Spring 5)
// Add spring-context-indexer dependency
// Generates META-INF/spring.components at compile time
// Avoids classpath scanning at runtime

// 4. Use Spring Boot DevTools for development
// Faster restarts using two classloaders

// 5. GraalVM Native Image (Spring Boot 3)
// AOT compilation - millisecond startup
// No runtime reflection/classpath scanning
```
