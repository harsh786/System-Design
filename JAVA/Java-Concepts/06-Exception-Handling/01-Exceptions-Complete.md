# Java Exception Handling - Complete Guide

## 1. Exception Hierarchy

```
                        Throwable
                       /         \
                      /           \
                   Error         Exception
                  /    \         /        \
                 /      \       /          \
     OutOfMemory  StackOverflow  RuntimeException   Checked Exceptions
     Error        Error          (Unchecked)
                                /    |    \          /    |    \
                               /     |     \        /     |     \
                     NullPointer  ClassCast  IllegalArg  IOException  SQLException
                     Exception    Exception  Exception   /      \
                                                        /        \
                                                FileNotFound  EOFException
```

### Complete Hierarchy

```java
/**
 * java.lang.Throwable (implements Serializable)
 * ├── java.lang.Error (DO NOT CATCH - JVM/system level)
 * │   ├── OutOfMemoryError
 * │   ├── StackOverflowError
 * │   ├── VirtualMachineError
 * │   ├── AssertionError
 * │   ├── LinkageError
 * │   │   ├── NoClassDefFoundError
 * │   │   └── UnsatisfiedLinkError
 * │   └── ExceptionInInitializerError
 * │
 * └── java.lang.Exception
 *     ├── RuntimeException (UNCHECKED - compiler doesn't enforce handling)
 *     │   ├── NullPointerException
 *     │   ├── ArrayIndexOutOfBoundsException
 *     │   ├── StringIndexOutOfBoundsException
 *     │   ├── IllegalArgumentException
 *     │   │   └── NumberFormatException
 *     │   ├── IllegalStateException
 *     │   ├── ClassCastException
 *     │   ├── UnsupportedOperationException
 *     │   ├── ArithmeticException
 *     │   ├── ConcurrentModificationException
 *     │   └── NoSuchElementException
 *     │
 *     └── Checked Exceptions (MUST be caught or declared)
 *         ├── IOException
 *         │   ├── FileNotFoundException
 *         │   ├── EOFException
 *         │   └── SocketException
 *         ├── SQLException
 *         ├── ClassNotFoundException
 *         ├── CloneNotSupportedException
 *         ├── InterruptedException
 *         ├── ReflectiveOperationException
 *         └── ParseException
 */
```

---

## 2. Checked vs Unchecked Exceptions

### Checked Exceptions

```java
/**
 * CHECKED EXCEPTIONS:
 * - Compiler FORCES you to handle (catch or declare in throws)
 * - Represent recoverable conditions
 * - External factors beyond program control
 * - Must be caught or propagated via "throws" clause
 */

// IOException - file/network operations
public String readFile(String path) throws IOException {
    BufferedReader reader = new BufferedReader(new FileReader(path));
    return reader.readLine();
}

// SQLException - database operations
public User findUser(int id) throws SQLException {
    Connection conn = dataSource.getConnection();
    PreparedStatement ps = conn.prepareStatement("SELECT * FROM users WHERE id = ?");
    ps.setInt(1, id);
    ResultSet rs = ps.executeQuery();
    // ...
}

// ClassNotFoundException - reflection
public Object createInstance(String className)
        throws ClassNotFoundException, InstantiationException, IllegalAccessException {
    Class<?> clazz = Class.forName(className);
    return clazz.getDeclaredConstructor().newInstance();
}

// InterruptedException - thread operations
public void waitForResult() throws InterruptedException {
    Thread.sleep(1000);
}
```

### Unchecked Exceptions (RuntimeException)

```java
/**
 * UNCHECKED EXCEPTIONS (RuntimeException subclasses):
 * - Compiler does NOT force handling
 * - Represent programming errors / bugs
 * - Should be prevented by proper coding (validation, null checks)
 * - Indicate violated preconditions
 */

// NullPointerException - accessing member on null reference
String s = null;
s.length();  // NPE!

// IllegalArgumentException - invalid method argument
public void setAge(int age) {
    if (age < 0 || age > 150) {
        throw new IllegalArgumentException("Age must be between 0 and 150, got: " + age);
    }
    this.age = age;
}

// IllegalStateException - method called at wrong time
public class Connection {
    private boolean closed = false;

    public void execute(String query) {
        if (closed) {
            throw new IllegalStateException("Connection is already closed");
        }
        // execute query
    }
}

// ArrayIndexOutOfBoundsException
int[] arr = {1, 2, 3};
int x = arr[5];  // ArrayIndexOutOfBoundsException!

// ClassCastException
Object obj = "Hello";
Integer num = (Integer) obj;  // ClassCastException!

// UnsupportedOperationException
List<String> immutable = Collections.unmodifiableList(list);
immutable.add("new");  // UnsupportedOperationException!

// NumberFormatException (subclass of IllegalArgumentException)
int n = Integer.parseInt("abc");  // NumberFormatException!

// ConcurrentModificationException
List<String> list = new ArrayList<>(Arrays.asList("a", "b", "c"));
for (String s : list) {
    list.remove(s);  // ConcurrentModificationException!
}
```

### When to Use Which

```java
/**
 * USE CHECKED EXCEPTIONS when:
 * - The caller can reasonably be expected to recover
 * - The failure is due to external conditions (file missing, network down)
 * - You want to FORCE the caller to handle the error
 *
 * USE UNCHECKED EXCEPTIONS when:
 * - The error is a programming bug (null pointer, invalid argument)
 * - The caller cannot reasonably recover
 * - Preconditions are violated
 * - The error indicates broken invariants
 *
 * GENERAL RULE:
 * If a client can reasonably recover → Checked
 * If it's a programming error → Unchecked (RuntimeException)
 */
```

---

## 3. Exception Handling Mechanisms

### try-catch-finally

```java
// Basic structure
public String readFirstLine(String path) {
    BufferedReader reader = null;
    try {
        reader = new BufferedReader(new FileReader(path));
        return reader.readLine();
    } catch (FileNotFoundException e) {
        System.err.println("File not found: " + path);
        return null;
    } catch (IOException e) {
        System.err.println("Error reading file: " + e.getMessage());
        return null;
    } finally {
        // ALWAYS executes (even if return in try/catch)
        if (reader != null) {
            try {
                reader.close();
            } catch (IOException e) {
                // Log but don't throw - don't mask original exception
            }
        }
    }
}
```

### Execution Order with Return in Finally

```java
// CRITICAL: finally block ALWAYS runs (except System.exit())
public static int testFinally() {
    try {
        System.out.println("try");
        return 1;
    } catch (Exception e) {
        System.out.println("catch");
        return 2;
    } finally {
        System.out.println("finally");
        // If you return here, it OVERRIDES the try/catch return!
        // return 3;  // BAD PRACTICE - masks the original return
    }
}
// Output: "try", "finally", returns 1

// Exception in finally can mask original exception
public static void dangerousFinally() throws Exception {
    try {
        throw new IOException("Original");
    } finally {
        throw new RuntimeException("In finally");
        // RuntimeException is thrown, IOException is LOST!
    }
}

// Order of execution:
// 1. try block executes
// 2. If exception: matching catch block executes
// 3. finally block ALWAYS executes
// 4. Return value is determined BEFORE finally, but finally still runs
// 5. If finally has a return, it overrides everything
```

### Multi-catch (Java 7+)

```java
// Before Java 7 - duplicate code
try {
    // risky operation
} catch (IOException e) {
    logger.error("Operation failed", e);
    throw new ServiceException(e);
} catch (SQLException e) {
    logger.error("Operation failed", e);  // Duplicate!
    throw new ServiceException(e);
}

// Java 7+ Multi-catch - single block for multiple exception types
try {
    // risky operation
} catch (IOException | SQLException | ParseException e) {
    // e is effectively final in multi-catch
    logger.error("Operation failed", e);
    throw new ServiceException(e);
}

// NOTE: Exception types in multi-catch cannot be related
// catch (FileNotFoundException | IOException e) {}  // COMPILE ERROR!
// FileNotFoundException IS-A IOException (redundant)

// The variable in multi-catch is implicitly final
try {
    // ...
} catch (IOException | SQLException e) {
    // e = new IOException();  // COMPILE ERROR - e is final
    throw e;  // OK - compiler tracks all possible types
}
```

### try-with-resources (Java 7+)

```java
// AutoCloseable interface - for try-with-resources
public interface AutoCloseable {
    void close() throws Exception;
}

// Resources are automatically closed (in reverse declaration order)
public String readFile(String path) throws IOException {
    try (BufferedReader reader = new BufferedReader(new FileReader(path));
         PrintWriter writer = new PrintWriter(new FileWriter("output.txt"))) {

        String line = reader.readLine();
        writer.println(line);
        return line;
    }
    // reader and writer are automatically closed here
    // Close order: writer first, then reader (reverse of declaration)
}

// Custom AutoCloseable
public class DatabaseConnection implements AutoCloseable {
    private Connection connection;

    public DatabaseConnection(String url) throws SQLException {
        this.connection = DriverManager.getConnection(url);
        System.out.println("Connection opened");
    }

    public ResultSet query(String sql) throws SQLException {
        return connection.createStatement().executeQuery(sql);
    }

    @Override
    public void close() throws SQLException {
        if (connection != null && !connection.isClosed()) {
            connection.close();
            System.out.println("Connection closed");
        }
    }
}

// Usage
try (DatabaseConnection db = new DatabaseConnection("jdbc:mysql://localhost/test")) {
    ResultSet rs = db.query("SELECT * FROM users");
    // process results
}  // db.close() called automatically

// Java 9+ : Can use effectively-final variables
BufferedReader reader = new BufferedReader(new FileReader(path));
try (reader) {  // Java 9+ allows this
    return reader.readLine();
}
```

### Suppressed Exceptions

```java
// When close() throws AND try block also throws
public class ProblematicResource implements AutoCloseable {
    public void doWork() throws Exception {
        throw new Exception("Exception from doWork");
    }

    @Override
    public void close() throws Exception {
        throw new Exception("Exception from close");
    }
}

// What happens:
try (ProblematicResource r = new ProblematicResource()) {
    r.doWork();  // Throws "Exception from doWork"
}
// close() also throws "Exception from close"
// "Exception from doWork" is the PRIMARY exception
// "Exception from close" is SUPPRESSED (attached to primary)

// Accessing suppressed exceptions:
try {
    try (ProblematicResource r = new ProblematicResource()) {
        r.doWork();
    }
} catch (Exception e) {
    System.out.println("Primary: " + e.getMessage());
    // "Primary: Exception from doWork"

    for (Throwable suppressed : e.getSuppressed()) {
        System.out.println("Suppressed: " + suppressed.getMessage());
        // "Suppressed: Exception from close"
    }
}

// Manually adding suppressed exceptions
public void process() throws Exception {
    Exception primary = null;
    try {
        // operation that might fail
    } catch (Exception e) {
        primary = e;
        throw e;
    } finally {
        try {
            // cleanup that might fail
        } catch (Exception e) {
            if (primary != null) {
                primary.addSuppressed(e);  // Attach to primary
            } else {
                throw e;
            }
        }
    }
}
```

### Custom Exceptions

```java
// Custom CHECKED exception
public class InsufficientFundsException extends Exception {
    private final double amount;
    private final double balance;

    public InsufficientFundsException(double amount, double balance) {
        super(String.format("Insufficient funds: tried to withdraw %.2f but balance is %.2f",
                amount, balance));
        this.amount = amount;
        this.balance = balance;
    }

    public InsufficientFundsException(String message, Throwable cause) {
        super(message, cause);
        this.amount = 0;
        this.balance = 0;
    }

    public double getAmount() { return amount; }
    public double getBalance() { return balance; }
}

// Custom UNCHECKED exception
public class EntityNotFoundException extends RuntimeException {
    private final String entityType;
    private final String entityId;

    public EntityNotFoundException(String entityType, String entityId) {
        super(String.format("%s not found with id: %s", entityType, entityId));
        this.entityType = entityType;
        this.entityId = entityId;
    }

    public EntityNotFoundException(String message, Throwable cause) {
        super(message, cause);
        this.entityType = "Unknown";
        this.entityId = "Unknown";
    }

    public String getEntityType() { return entityType; }
    public String getEntityId() { return entityId; }
}

// Usage
public class BankAccount {
    private double balance;

    public void withdraw(double amount) throws InsufficientFundsException {
        if (amount > balance) {
            throw new InsufficientFundsException(amount, balance);
        }
        balance -= amount;
    }
}

public class UserService {
    public User findById(String id) {
        User user = repository.findById(id);
        if (user == null) {
            throw new EntityNotFoundException("User", id);  // Unchecked - no throws needed
        }
        return user;
    }
}
```

---

## 4. Best Practices

### Never Catch Exception/Throwable Broadly

```java
// BAD - catches everything including programming errors
try {
    processOrder(order);
} catch (Exception e) {  // Catches NPE, IndexOutOfBounds, etc.!
    logger.error("Failed", e);
}

// WORSE - catches JVM errors too!
try {
    processOrder(order);
} catch (Throwable t) {  // Catches OutOfMemoryError!
    // You can't recover from OOM
}

// GOOD - catch specific exceptions
try {
    processOrder(order);
} catch (PaymentDeclinedException e) {
    notifyCustomer(e.getReason());
} catch (InventoryException e) {
    backorderItem(e.getProductId());
} catch (IOException e) {
    retryWithBackoff();
}
```

### Don't Use Exceptions for Flow Control

```java
// BAD - using exception for normal flow
public boolean isInteger(String s) {
    try {
        Integer.parseInt(s);
        return true;
    } catch (NumberFormatException e) {
        return false;  // Using exception as flow control!
    }
}

// GOOD - check condition before operation
public Optional<Integer> parseInteger(String s) {
    if (s == null || s.isEmpty()) return Optional.empty();
    // Still need try-catch for truly invalid input, but avoid for expected cases
    try {
        return Optional.of(Integer.parseInt(s));
    } catch (NumberFormatException e) {
        return Optional.empty();
    }
}

// BAD - iterating with exception
try {
    int i = 0;
    while (true) {
        array[i++].process();  // Throws ArrayIndexOutOfBoundsException to stop
    }
} catch (ArrayIndexOutOfBoundsException e) {
    // "Done" - terrible!
}

// GOOD
for (int i = 0; i < array.length; i++) {
    array[i].process();
}
```

### Exception Translation and Chaining

```java
/**
 * Exception Translation: Convert low-level exception to higher-level one
 * Exception Chaining: Preserve original cause
 */

// Service layer translates data layer exceptions
public class OrderService {

    public Order createOrder(OrderRequest request) {
        try {
            validateOrder(request);
            Order order = buildOrder(request);
            return orderRepository.save(order);
        } catch (SQLException e) {
            // TRANSLATE: Low-level DB exception → meaningful business exception
            // CHAIN: Preserve original cause
            throw new OrderCreationException(
                "Failed to create order for customer: " + request.getCustomerId(),
                e  // Original cause preserved!
            );
        } catch (ValidationException e) {
            // Re-throw domain exceptions as-is
            throw e;
        }
    }
}

// Accessing the cause chain
try {
    orderService.createOrder(request);
} catch (OrderCreationException e) {
    logger.error("Order failed: " + e.getMessage());
    // Access original cause
    Throwable rootCause = e.getCause();  // The original SQLException
    if (rootCause instanceof SQLException) {
        logger.error("SQL Error Code: " + ((SQLException) rootCause).getErrorCode());
    }
}

// Finding root cause utility
public static Throwable getRootCause(Throwable throwable) {
    Throwable cause = throwable;
    while (cause.getCause() != null && cause.getCause() != cause) {
        cause = cause.getCause();
    }
    return cause;
}
```

### Documenting Exceptions

```java
/**
 * Processes a payment for the given order.
 *
 * @param order the order to process payment for
 * @param paymentMethod the payment method to charge
 * @return the payment confirmation
 * @throws IllegalArgumentException if order is null or has no items
 * @throws IllegalStateException if order is already paid
 * @throws PaymentDeclinedException if the payment gateway declines the charge
 * @throws PaymentGatewayException if communication with payment gateway fails
 */
public PaymentConfirmation processPayment(Order order, PaymentMethod paymentMethod)
        throws PaymentDeclinedException, PaymentGatewayException {

    Objects.requireNonNull(order, "Order must not be null");
    if (order.getItems().isEmpty()) {
        throw new IllegalArgumentException("Order must have at least one item");
    }
    if (order.isPaid()) {
        throw new IllegalStateException("Order " + order.getId() + " is already paid");
    }
    // Process payment...
}
```

### Additional Best Practices

```java
// 1. Prefer standard exceptions
throw new IllegalArgumentException("Port must be between 0 and 65535");
throw new IllegalStateException("Service not initialized");
throw new UnsupportedOperationException("Read-only collection");
throw new NullPointerException("Connection string must not be null");

// 2. Include context in exception messages
// BAD:
throw new IOException("Write failed");
// GOOD:
throw new IOException(String.format(
    "Failed to write %d bytes to file '%s': disk full", byteCount, filePath));

// 3. Fail fast - validate early
public void transferMoney(Account from, Account to, BigDecimal amount) {
    // Validate ALL preconditions upfront
    Objects.requireNonNull(from, "Source account must not be null");
    Objects.requireNonNull(to, "Destination account must not be null");
    Objects.requireNonNull(amount, "Amount must not be null");
    if (amount.compareTo(BigDecimal.ZERO) <= 0) {
        throw new IllegalArgumentException("Amount must be positive: " + amount);
    }
    // Now proceed with operation...
}

// 4. Don't ignore exceptions
try {
    resource.close();
} catch (IOException e) {
    // BAD: empty catch block
}

try {
    resource.close();
} catch (IOException e) {
    logger.warn("Failed to close resource", e);  // At minimum, log it
}

// 5. Throw early, catch late
// Throw at the point of failure (don't propagate null/invalid state)
// Catch at the point where you can meaningfully handle it
```

---

## 5. Exceptions in Multi-threading

### UncaughtExceptionHandler

```java
// Exceptions in threads are NOT propagated to the calling thread
// They simply kill the thread silently unless handled

// Setting handler for a specific thread
Thread thread = new Thread(() -> {
    throw new RuntimeException("Thread failed!");
});
thread.setUncaughtExceptionHandler((t, e) -> {
    System.err.println("Thread " + t.getName() + " failed: " + e.getMessage());
    // Log, alert, restart logic here
});
thread.start();

// Global default handler for ALL threads
Thread.setDefaultUncaughtExceptionHandler((t, e) -> {
    System.err.println("Unhandled exception in thread " + t.getName());
    e.printStackTrace();
    // Send to monitoring system
    alerting.sendAlert("Thread crashed", e);
});

// Custom ThreadFactory with exception handling
public class MonitoredThreadFactory implements ThreadFactory {
    private final String namePrefix;
    private final AtomicInteger counter = new AtomicInteger(1);
    private final Thread.UncaughtExceptionHandler handler;

    public MonitoredThreadFactory(String namePrefix,
                                   Thread.UncaughtExceptionHandler handler) {
        this.namePrefix = namePrefix;
        this.handler = handler;
    }

    @Override
    public Thread newThread(Runnable r) {
        Thread t = new Thread(r, namePrefix + "-" + counter.getAndIncrement());
        t.setUncaughtExceptionHandler(handler);
        return t;
    }
}
```

### Exceptions in ExecutorService

```java
// PROBLEM: ExecutorService swallows exceptions silently!

ExecutorService executor = Executors.newFixedThreadPool(4);

// With execute() - exception goes to UncaughtExceptionHandler
executor.execute(() -> {
    throw new RuntimeException("Oops!");
    // Goes to UncaughtExceptionHandler (or kills thread silently)
});

// With submit() - exception is captured in Future
Future<?> future = executor.submit(() -> {
    throw new RuntimeException("Oops!");
    // Exception is NOT thrown now - it's stored in the Future
});

// Exception surfaces when you call get()
try {
    future.get();  // Blocks until task completes
} catch (ExecutionException e) {
    // The ACTUAL exception is wrapped in ExecutionException
    Throwable actualException = e.getCause();
    System.out.println(actualException.getMessage());  // "Oops!"
} catch (InterruptedException e) {
    Thread.currentThread().interrupt();
}

// With Callable<V> - same behavior
Future<String> resultFuture = executor.submit(() -> {
    if (someCondition) {
        throw new IOException("Network error");
    }
    return "Success";
});

try {
    String result = resultFuture.get(5, TimeUnit.SECONDS);
} catch (ExecutionException e) {
    // Unwrap to get the real exception
    if (e.getCause() instanceof IOException) {
        handleNetworkError((IOException) e.getCause());
    }
} catch (TimeoutException e) {
    future.cancel(true);
} catch (InterruptedException e) {
    Thread.currentThread().interrupt();
}

// CompletableFuture exception handling
CompletableFuture<Order> orderFuture = CompletableFuture
    .supplyAsync(() -> fetchOrder(orderId))
    .thenApply(order -> enrichOrder(order))
    .exceptionally(ex -> {
        // Handle exception, return fallback
        logger.error("Failed to fetch order", ex);
        return Order.empty();
    });

// More granular CompletableFuture error handling
CompletableFuture<Result> pipeline = CompletableFuture
    .supplyAsync(() -> riskyOperation())
    .handle((result, exception) -> {
        if (exception != null) {
            // Log and transform
            logger.error("Pipeline failed", exception);
            return Result.failure(exception.getMessage());
        }
        return Result.success(result);
    })
    .whenComplete((result, exception) -> {
        // Always runs - cleanup, metrics, etc.
        metrics.recordCompletion(result != null);
    });

// invokeAll - all tasks complete, check each Future
List<Callable<String>> tasks = Arrays.asList(
    () -> riskyTask1(),
    () -> riskyTask2(),
    () -> riskyTask3()
);

List<Future<String>> futures = executor.invokeAll(tasks);
for (Future<String> f : futures) {
    try {
        String result = f.get();
        process(result);
    } catch (ExecutionException e) {
        handleFailure(e.getCause());
    }
}
```

### Exception Handling Patterns for Thread Pools

```java
// Pattern: Wrapper that catches and logs exceptions
public class SafeRunnable implements Runnable {
    private final Runnable delegate;
    private final BiConsumer<Runnable, Throwable> errorHandler;

    public SafeRunnable(Runnable delegate, BiConsumer<Runnable, Throwable> errorHandler) {
        this.delegate = delegate;
        this.errorHandler = errorHandler;
    }

    @Override
    public void run() {
        try {
            delegate.run();
        } catch (Throwable t) {
            errorHandler.accept(delegate, t);
        }
    }
}

// Usage
executor.execute(new SafeRunnable(
    () -> processOrder(order),
    (task, error) -> logger.error("Task failed", error)
));

// Pattern: Custom ThreadPoolExecutor with afterExecute hook
public class MonitoredThreadPool extends ThreadPoolExecutor {

    public MonitoredThreadPool(int coreSize, int maxSize, long keepAlive,
                               TimeUnit unit, BlockingQueue<Runnable> queue) {
        super(coreSize, maxSize, keepAlive, unit, queue);
    }

    @Override
    protected void afterExecute(Runnable r, Throwable t) {
        super.afterExecute(r, t);

        // For execute() - throwable is passed directly
        if (t != null) {
            handleException(t);
        }

        // For submit() - need to extract from Future
        if (t == null && r instanceof Future<?>) {
            try {
                Future<?> future = (Future<?>) r;
                if (future.isDone()) {
                    future.get();  // Will throw ExecutionException if task failed
                }
            } catch (ExecutionException e) {
                handleException(e.getCause());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } catch (CancellationException e) {
                // Task was cancelled - might be expected
            }
        }
    }

    private void handleException(Throwable t) {
        logger.error("Task execution failed", t);
        metrics.incrementErrorCount();
    }
}
```

---

## 6. Custom Exception Hierarchy for LLD

### Complete E-Commerce Exception System

```java
/**
 * Exception hierarchy for an e-commerce system:
 *
 * BaseException (abstract)
 * ├── BusinessException (abstract - business rule violations)
 * │   ├── InsufficientFundsException
 * │   ├── OrderLimitExceededException
 * │   ├── ProductUnavailableException
 * │   └── CouponExpiredException
 * ├── ValidationException (input validation failures)
 * │   ├── InvalidEmailException
 * │   ├── InvalidQuantityException
 * │   └── MissingRequiredFieldException
 * ├── ResourceNotFoundException (entity not found)
 * │   ├── UserNotFoundException
 * │   ├── ProductNotFoundException
 * │   └── OrderNotFoundException
 * ├── ConflictException (state conflicts)
 * │   ├── DuplicateEmailException
 * │   └── ConcurrentModificationException
 * ├── AuthenticationException (identity verification)
 * │   ├── InvalidCredentialsException
 * │   └── TokenExpiredException
 * ├── AuthorizationException (permission denied)
 * │   └── InsufficientPermissionsException
 * └── InfrastructureException (technical failures)
 *     ├── DatabaseException
 *     ├── ExternalServiceException
 *     └── MessageQueueException
 */

// ============================================================
// BASE EXCEPTION
// ============================================================

public abstract class BaseException extends RuntimeException {
    private final String errorCode;
    private final ErrorSeverity severity;
    private final Map<String, Object> context;
    private final LocalDateTime timestamp;

    protected BaseException(String message, String errorCode, ErrorSeverity severity) {
        super(message);
        this.errorCode = errorCode;
        this.severity = severity;
        this.context = new HashMap<>();
        this.timestamp = LocalDateTime.now();
    }

    protected BaseException(String message, String errorCode,
                           ErrorSeverity severity, Throwable cause) {
        super(message, cause);
        this.errorCode = errorCode;
        this.severity = severity;
        this.context = new HashMap<>();
        this.timestamp = LocalDateTime.now();
    }

    public BaseException addContext(String key, Object value) {
        this.context.put(key, value);
        return this;
    }

    public String getErrorCode() { return errorCode; }
    public ErrorSeverity getSeverity() { return severity; }
    public Map<String, Object> getContext() { return Collections.unmodifiableMap(context); }
    public LocalDateTime getTimestamp() { return timestamp; }

    // For API responses
    public ErrorResponse toErrorResponse() {
        return new ErrorResponse(errorCode, getMessage(), context, timestamp);
    }
}

public enum ErrorSeverity {
    LOW,       // User input errors, expected failures
    MEDIUM,    // Business rule violations
    HIGH,      // System errors, needs investigation
    CRITICAL   // Infrastructure failures, needs immediate action
}

// ============================================================
// BUSINESS EXCEPTIONS
// ============================================================

public abstract class BusinessException extends BaseException {
    protected BusinessException(String message, String errorCode) {
        super(message, errorCode, ErrorSeverity.MEDIUM);
    }
}

public class InsufficientFundsException extends BusinessException {
    private final BigDecimal required;
    private final BigDecimal available;

    public InsufficientFundsException(BigDecimal required, BigDecimal available) {
        super(
            String.format("Insufficient funds: required %.2f, available %.2f",
                required, available),
            "PAYMENT_001"
        );
        this.required = required;
        this.available = available;
        addContext("required", required);
        addContext("available", available);
        addContext("deficit", required.subtract(available));
    }

    public BigDecimal getRequired() { return required; }
    public BigDecimal getAvailable() { return available; }
}

public class ProductUnavailableException extends BusinessException {
    private final String productId;
    private final int requestedQuantity;
    private final int availableQuantity;

    public ProductUnavailableException(String productId, int requested, int available) {
        super(
            String.format("Product %s: requested %d, only %d available",
                productId, requested, available),
            "INVENTORY_001"
        );
        this.productId = productId;
        this.requestedQuantity = requested;
        this.availableQuantity = available;
        addContext("productId", productId);
        addContext("requested", requested);
        addContext("available", available);
    }

    public String getProductId() { return productId; }
    public int getRequestedQuantity() { return requestedQuantity; }
    public int getAvailableQuantity() { return availableQuantity; }
}

public class OrderLimitExceededException extends BusinessException {
    public OrderLimitExceededException(String userId, int limit) {
        super(
            String.format("User %s exceeded order limit of %d per day", userId, limit),
            "ORDER_001"
        );
        addContext("userId", userId);
        addContext("limit", limit);
    }
}

// ============================================================
// VALIDATION EXCEPTIONS
// ============================================================

public class ValidationException extends BaseException {
    private final List<FieldError> fieldErrors;

    public ValidationException(String message, List<FieldError> fieldErrors) {
        super(message, "VALIDATION_001", ErrorSeverity.LOW);
        this.fieldErrors = fieldErrors;
        addContext("fieldErrors", fieldErrors);
    }

    public ValidationException(String field, String message) {
        this("Validation failed", List.of(new FieldError(field, message)));
    }

    public List<FieldError> getFieldErrors() { return fieldErrors; }

    // Builder for multiple validation errors
    public static ValidationExceptionBuilder builder() {
        return new ValidationExceptionBuilder();
    }

    public static class ValidationExceptionBuilder {
        private final List<FieldError> errors = new ArrayList<>();

        public ValidationExceptionBuilder addError(String field, String message) {
            errors.add(new FieldError(field, message));
            return this;
        }

        public ValidationExceptionBuilder addErrorIf(boolean condition, String field, String msg) {
            if (condition) errors.add(new FieldError(field, msg));
            return this;
        }

        public boolean hasErrors() { return !errors.isEmpty(); }

        public void throwIfErrors() {
            if (!errors.isEmpty()) {
                throw new ValidationException("Validation failed: " + errors.size() + " errors", errors);
            }
        }
    }
}

public record FieldError(String field, String message) {}

// Usage
public void validateOrder(OrderRequest request) {
    ValidationException.builder()
        .addErrorIf(request.getCustomerId() == null, "customerId", "Customer ID is required")
        .addErrorIf(request.getItems().isEmpty(), "items", "At least one item is required")
        .addErrorIf(request.getTotal().compareTo(BigDecimal.ZERO) <= 0, "total", "Total must be positive")
        .throwIfErrors();
}

// ============================================================
// RESOURCE NOT FOUND EXCEPTIONS
// ============================================================

public class ResourceNotFoundException extends BaseException {
    private final String resourceType;
    private final String resourceId;

    public ResourceNotFoundException(String resourceType, String resourceId) {
        super(
            String.format("%s not found with id: %s", resourceType, resourceId),
            "NOT_FOUND_001",
            ErrorSeverity.LOW
        );
        this.resourceType = resourceType;
        this.resourceId = resourceId;
        addContext("resourceType", resourceType);
        addContext("resourceId", resourceId);
    }

    public String getResourceType() { return resourceType; }
    public String getResourceId() { return resourceId; }
}

// Specific not-found exceptions (optional - can just use ResourceNotFoundException)
public class UserNotFoundException extends ResourceNotFoundException {
    public UserNotFoundException(String userId) {
        super("User", userId);
    }
}

public class ProductNotFoundException extends ResourceNotFoundException {
    public ProductNotFoundException(String productId) {
        super("Product", productId);
    }
}

public class OrderNotFoundException extends ResourceNotFoundException {
    public OrderNotFoundException(String orderId) {
        super("Order", orderId);
    }
}

// ============================================================
// CONFLICT EXCEPTIONS
// ============================================================

public class ConflictException extends BaseException {
    public ConflictException(String message, String errorCode) {
        super(message, errorCode, ErrorSeverity.MEDIUM);
    }
}

public class DuplicateResourceException extends ConflictException {
    public DuplicateResourceException(String resourceType, String field, String value) {
        super(
            String.format("%s already exists with %s: %s", resourceType, field, value),
            "CONFLICT_001"
        );
        addContext("resourceType", resourceType);
        addContext("field", field);
        addContext("value", value);
    }
}

public class OptimisticLockException extends ConflictException {
    public OptimisticLockException(String resourceType, String resourceId, long expectedVersion) {
        super(
            String.format("%s %s was modified by another user (expected version: %d)",
                resourceType, resourceId, expectedVersion),
            "CONFLICT_002"
        );
        addContext("resourceType", resourceType);
        addContext("resourceId", resourceId);
        addContext("expectedVersion", expectedVersion);
    }
}

// ============================================================
// AUTHENTICATION & AUTHORIZATION EXCEPTIONS
// ============================================================

public class AuthenticationException extends BaseException {
    public AuthenticationException(String message) {
        super(message, "AUTH_001", ErrorSeverity.MEDIUM);
    }
}

public class InvalidCredentialsException extends AuthenticationException {
    public InvalidCredentialsException() {
        super("Invalid username or password");
        // Never reveal which field is wrong!
    }
}

public class TokenExpiredException extends AuthenticationException {
    public TokenExpiredException(LocalDateTime expiredAt) {
        super("Authentication token expired at: " + expiredAt);
        addContext("expiredAt", expiredAt);
    }
}

public class AuthorizationException extends BaseException {
    public AuthorizationException(String userId, String resource, String action) {
        super(
            String.format("User %s is not authorized to %s on %s", userId, action, resource),
            "AUTHZ_001",
            ErrorSeverity.MEDIUM
        );
        addContext("userId", userId);
        addContext("resource", resource);
        addContext("action", action);
    }
}

// ============================================================
// INFRASTRUCTURE EXCEPTIONS
// ============================================================

public class InfrastructureException extends BaseException {
    public InfrastructureException(String message, String errorCode, Throwable cause) {
        super(message, errorCode, ErrorSeverity.HIGH, cause);
    }
}

public class DatabaseException extends InfrastructureException {
    public DatabaseException(String operation, Throwable cause) {
        super("Database operation failed: " + operation, "INFRA_DB_001", cause);
        addContext("operation", operation);
    }
}

public class ExternalServiceException extends InfrastructureException {
    public ExternalServiceException(String serviceName, int statusCode, Throwable cause) {
        super(
            String.format("External service '%s' failed with status %d", serviceName, statusCode),
            "INFRA_EXT_001",
            cause
        );
        addContext("serviceName", serviceName);
        addContext("statusCode", statusCode);
    }
}

// ============================================================
// ERROR RESPONSE (for API layer)
// ============================================================

public record ErrorResponse(
    String errorCode,
    String message,
    Map<String, Object> details,
    LocalDateTime timestamp
) {}

// ============================================================
// GLOBAL EXCEPTION HANDLER (Service layer)
// ============================================================

public class GlobalExceptionHandler {

    private static final Logger logger = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    public ErrorResponse handle(BaseException ex) {
        switch (ex.getSeverity()) {
            case LOW -> logger.info("Expected error: {}", ex.getMessage());
            case MEDIUM -> logger.warn("Business error: {}", ex.getMessage());
            case HIGH -> logger.error("System error: {}", ex.getMessage(), ex);
            case CRITICAL -> {
                logger.error("CRITICAL error: {}", ex.getMessage(), ex);
                alertService.sendCriticalAlert(ex);
            }
        }
        return ex.toErrorResponse();
    }

    // Map exceptions to HTTP-like status codes
    public int getStatusCode(BaseException ex) {
        return switch (ex) {
            case ValidationException v -> 400;
            case AuthenticationException a -> 401;
            case AuthorizationException a -> 403;
            case ResourceNotFoundException r -> 404;
            case ConflictException c -> 409;
            case BusinessException b -> 422;
            case InfrastructureException i -> 503;
            default -> 500;
        };
    }
}

// ============================================================
// COMPLETE USAGE IN SERVICE LAYER
// ============================================================

public class OrderService {
    private final UserRepository userRepository;
    private final ProductRepository productRepository;
    private final OrderRepository orderRepository;
    private final PaymentService paymentService;

    public Order createOrder(CreateOrderRequest request) {
        // 1. Validation
        validateRequest(request);

        // 2. Check user exists
        User user = userRepository.findById(request.getUserId())
            .orElseThrow(() -> new UserNotFoundException(request.getUserId()));

        // 3. Check order limits
        long todayOrders = orderRepository.countTodayOrders(user.getId());
        if (todayOrders >= user.getDailyOrderLimit()) {
            throw new OrderLimitExceededException(user.getId(), user.getDailyOrderLimit());
        }

        // 4. Validate products and inventory
        List<OrderItem> items = new ArrayList<>();
        for (ItemRequest itemReq : request.getItems()) {
            Product product = productRepository.findById(itemReq.getProductId())
                .orElseThrow(() -> new ProductNotFoundException(itemReq.getProductId()));

            if (product.getStock() < itemReq.getQuantity()) {
                throw new ProductUnavailableException(
                    product.getId(), itemReq.getQuantity(), product.getStock());
            }

            items.add(new OrderItem(product, itemReq.getQuantity()));
        }

        // 5. Process payment
        BigDecimal total = calculateTotal(items);
        try {
            paymentService.charge(user.getPaymentMethod(), total);
        } catch (PaymentGatewayException e) {
            // Translate infrastructure exception to business exception
            throw new InsufficientFundsException(total, user.getBalance());
        }

        // 6. Create and persist order
        Order order = new Order(user, items, total);
        try {
            return orderRepository.save(order);
        } catch (Exception e) {
            // Compensate: refund payment
            paymentService.refund(user.getPaymentMethod(), total);
            throw new DatabaseException("save order", e);
        }
    }

    private void validateRequest(CreateOrderRequest request) {
        ValidationException.builder()
            .addErrorIf(request.getUserId() == null, "userId", "User ID is required")
            .addErrorIf(request.getItems() == null || request.getItems().isEmpty(),
                "items", "At least one item is required")
            .addErrorIf(request.getItems() != null && request.getItems().size() > 100,
                "items", "Cannot order more than 100 items at once")
            .throwIfErrors();
    }
}

// ============================================================
// USING IN TESTS
// ============================================================

// JUnit 5 testing custom exceptions
class OrderServiceTest {

    @Test
    void shouldThrowUserNotFound_whenUserDoesNotExist() {
        CreateOrderRequest request = new CreateOrderRequest("nonexistent-user", items);

        UserNotFoundException ex = assertThrows(
            UserNotFoundException.class,
            () -> orderService.createOrder(request)
        );

        assertEquals("User", ex.getResourceType());
        assertEquals("nonexistent-user", ex.getResourceId());
        assertEquals("NOT_FOUND_001", ex.getErrorCode());
    }

    @Test
    void shouldThrowValidationException_whenNoItems() {
        CreateOrderRequest request = new CreateOrderRequest("user-1", List.of());

        ValidationException ex = assertThrows(
            ValidationException.class,
            () -> orderService.createOrder(request)
        );

        assertTrue(ex.getFieldErrors().stream()
            .anyMatch(e -> e.field().equals("items")));
    }

    @Test
    void shouldThrowProductUnavailable_whenInsufficientStock() {
        when(productRepository.findById("P1")).thenReturn(Optional.of(productWithStock(2)));
        CreateOrderRequest request = createRequest("user-1", "P1", 5);

        ProductUnavailableException ex = assertThrows(
            ProductUnavailableException.class,
            () -> orderService.createOrder(request)
        );

        assertEquals("P1", ex.getProductId());
        assertEquals(5, ex.getRequestedQuantity());
        assertEquals(2, ex.getAvailableQuantity());
    }
}
```

---

## Quick Reference: Exception Handling Cheat Sheet

| Scenario | Exception Type | Example |
|----------|---------------|---------|
| Invalid method argument | `IllegalArgumentException` | age < 0 |
| Null where not allowed | `NullPointerException` | null parameter |
| Wrong object state | `IllegalStateException` | closed connection |
| Not found | Custom `NotFoundException` | user not in DB |
| Business rule violated | Custom `BusinessException` | insufficient funds |
| Input validation failed | Custom `ValidationException` | invalid email format |
| Duplicate resource | Custom `ConflictException` | email already exists |
| External service failure | Custom `InfrastructureException` | payment gateway down |
| Permission denied | Custom `AuthorizationException` | user can't delete |
| Operation not supported | `UnsupportedOperationException` | immutable collection |

```java
// Decision flow for choosing exception type:
// 1. Is it a programming error? → RuntimeException (unchecked)
// 2. Can caller recover? → Checked exception
// 3. Is it a business rule? → Custom BusinessException (unchecked)
// 4. Is it external failure? → Custom InfrastructureException (unchecked, HIGH severity)
// 5. Is it missing data? → Custom NotFoundException (unchecked)
// 6. Is it invalid input? → Custom ValidationException (unchecked)
```
