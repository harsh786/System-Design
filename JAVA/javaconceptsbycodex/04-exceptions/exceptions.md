# Exceptions

Exceptions represent abnormal control flow. In LLD, exception design decides how failures move through the system.

## Exception Hierarchy

```text
Throwable
|
+-- Error
|   +-- OutOfMemoryError
|   +-- StackOverflowError
|
+-- Exception
    +-- IOException
    +-- SQLException
    +-- RuntimeException
        +-- NullPointerException
        +-- IllegalArgumentException
        +-- IllegalStateException
        +-- IndexOutOfBoundsException
```

## Checked Exceptions

Checked exceptions must be caught or declared.

```java
static String readFile(Path path) throws IOException {
    return Files.readString(path);
}
```

Use checked exceptions when callers can reasonably recover and you want the compiler to force handling.

## Unchecked Exceptions

Unchecked exceptions extend `RuntimeException`. They do not need to be declared.

```java
if (amount <= 0) {
    throw new IllegalArgumentException("amount must be positive");
}
```

Use unchecked exceptions for programming errors, invalid state, and domain validation failures where forcing every caller to catch is noisy.

## Error

`Error` represents serious JVM-level problems. Application code usually should not catch `Error`.

Examples:

- `OutOfMemoryError`
- `StackOverflowError`
- `NoClassDefFoundError`

## try/catch/finally

```java
try {
    service.process(order);
} catch (PaymentFailedException ex) {
    logger.warn("payment failed", ex);
} finally {
    metrics.increment("order.process.attempt");
}
```

`finally` runs whether the try block succeeds or fails, except in extreme cases like JVM termination.

## try-with-resources

Use this for resources implementing `AutoCloseable`.

```java
try (BufferedReader reader = Files.newBufferedReader(path)) {
    return reader.readLine();
}
```

The resource is closed automatically.

## Custom Exception

```java
class InsufficientBalanceException extends RuntimeException {
    InsufficientBalanceException(String accountId, int available, int requested) {
        super("Account " + accountId + " has " + available + " but requested " + requested);
    }
}
```

Use custom exceptions when they represent a meaningful domain failure.

## Common Built-In Exceptions

| Exception | When to use |
|---|---|
| `IllegalArgumentException` | Caller passed invalid argument |
| `IllegalStateException` | Object is not in a valid state for this operation |
| `UnsupportedOperationException` | Operation not supported by implementation |
| `NoSuchElementException` | Requested value absent |
| `TimeoutException` | Operation timed out |
| `ConcurrentModificationException` | Fail-fast iteration detected structural modification |

## Exception Design For LLD

Use exceptions for failures that prevent the requested operation from completing.

Example:

```java
class ParkingLot {
    Ticket park(Vehicle vehicle) {
        ParkingSpot spot = findSpot(vehicle)
            .orElseThrow(() -> new NoSpotAvailableException(vehicle.type()));
        return allocate(vehicle, spot);
    }
}
```

Do not use exceptions for normal branching when absence is expected:

```java
Optional<User> findById(UserId id);
```

## Best Practices

- Throw specific exceptions.
- Include useful context in messages.
- Do not swallow exceptions silently.
- Preserve the cause when wrapping exceptions.
- Do not catch `Exception` unless you are at a boundary.
- Avoid checked exceptions in deeply layered business code unless recovery is real.
- Avoid returning `null` for failure when `Optional`, result objects, or exceptions express intent better.

Runnable example: `src/main/java/com/codex/javaconcepts/exceptions/ExceptionExamples.java`

