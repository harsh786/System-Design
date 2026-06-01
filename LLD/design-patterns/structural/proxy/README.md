# Proxy Design Pattern

## What Is It?

The Proxy pattern provides a surrogate or placeholder for another object to control access to it. The proxy implements the same interface as the real object and delegates requests to it, optionally adding behavior before/after.

## When to Use

- Object creation is expensive (lazy initialization)
- Access control is needed
- You want to cache results transparently
- You need logging/monitoring without modifying the real object
- The real object is remote (network proxy)

## Why Use It

- Separates concerns (access control, caching, logging) from business logic
- Client code doesn't change - it works with the same interface
- Follows Open/Closed Principle - add behavior without modifying existing code

---

## Class Diagram (ASCII)

```
        +----------------+
        |   <<interface>>|
        |     Subject     |
        +----------------+
        | + request()    |
        +-------+--------+
                |
       +--------+--------+
       |                 |
+------+------+   +------+------+
|  RealSubject |   |    Proxy    |
+--------------+   +-------------+
| + request() |   | - real: Subject
+--------------+   | + request() |----> delegates to RealSubject
                   +-------------+
```

---

## Types of Proxies

| Type | Purpose | Example |
|------|---------|---------|
| **Virtual** | Lazy initialization of expensive objects | Load image only when displayed |
| **Remote** | Represent object in different address space | Java RMI stub |
| **Protection** | Access control based on permissions | Role-based document access |
| **Caching** | Store results to avoid repeated computation | Database query cache |
| **Logging** | Add logging/metrics around calls | Method timing, audit trails |

---

## Real-World Use Cases

1. **Hibernate Lazy Loading** - Entity proxies that load from DB only on first access
2. **Spring AOP** - Proxies that add transactions, security, caching around beans
3. **Java RMI** - Stubs act as proxies for remote objects
4. **CDN Caching** - CDN proxies cache origin server responses
5. **API Rate Limiting** - Proxy counts requests and rejects when limit exceeded

---

## Proxy vs Decorator

| Aspect | Proxy | Decorator |
|--------|-------|-----------|
| **Intent** | Control access | Add behavior |
| **Who creates real object** | Proxy often creates it | Client passes it in |
| **Relationship** | Proxy knows concrete class | Decorator knows only interface |
| **Transparency** | Client doesn't know about real object | Client wraps explicitly |
| **Lifecycle** | Manages lifecycle of real object | Doesn't own the wrapped object |

---

## Pros and Cons

### Pros
- Open/Closed Principle - new proxies without changing real objects
- Single Responsibility - separate cross-cutting concerns
- Lazy initialization saves resources
- Client code is unaware of the proxy
- Can manage object lifecycle

### Cons
- Adds indirection (slight performance overhead)
- Increases number of classes
- Response might be delayed on first access (virtual proxy)
- Can make debugging harder (hidden delegation)

---

## When NOT to Use

- Simple objects that are cheap to create (overhead not justified)
- When direct access is required for performance-critical paths
- If the interface is unstable (proxy must mirror every change)
- When AOP frameworks already provide the behavior you need (don't reinvent)
