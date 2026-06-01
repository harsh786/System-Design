# Chain of Responsibility Design Pattern

## What Is It?

The Chain of Responsibility is a behavioral design pattern that lets you pass requests along a chain of handlers. Each handler decides either to process the request or to pass it to the next handler in the chain.

## When to Use

- When multiple objects may handle a request and the handler isn't known in advance
- When you want to issue a request without specifying the receiver explicitly
- When the set of handlers should be specified dynamically

## Why Use It

- **Decouples** sender and receiver of requests
- **Single Responsibility** - each handler does one thing
- **Open/Closed** - add new handlers without modifying existing code
- **Flexible ordering** - chain can be composed at runtime

---

## Class Diagram (ASCII)

```
┌─────────────────────┐
│     <<interface>>    │
│       Handler        │
├─────────────────────┤
│ + setNext(Handler)  │
│ + handle(Request)   │
└────────┬────────────┘
         │ implements
         ▼
┌─────────────────────┐       next       ┌─────────────────────┐
│    BaseHandler       │─────────────────▶│      Handler        │
├─────────────────────┤                   └─────────────────────┘
│ - next: Handler      │
│ + setNext(Handler)   │
│ + handle(Request)    │
└────────┬────────────┘
         │ extends
    ┌────┼────────┬──────────────┐
    ▼    ▼        ▼              ▼
┌───────┐ ┌────────┐ ┌──────────┐ ┌──────────────┐
│Handler│ │Handler │ │ Handler  │ │   Handler    │
│   A   │ │   B    │ │    C     │ │      D       │
└───────┘ └────────┘ └──────────┘ └──────────────┘

Request Flow:
  Client ──▶ [A] ──▶ [B] ──▶ [C] ──▶ [D] ──▶ (end)
                       │
                       ▼ (can stop here)
                    Response
```

---

## Real-World Use Cases

| Use Case | Example |
|----------|---------|
| **Servlet Filters** | Java EE filter chain (auth, logging, compression) |
| **Middleware Pipelines** | Express.js/ASP.NET middleware, Spring interceptors |
| **Exception Handling** | Try-catch chains, error propagation up call stack |
| **Event Bubbling** | DOM event propagation (capture → target → bubble) |
| **Approval Workflows** | Purchase orders requiring manager → VP → CEO approval |
| **Logging** | Log4j appenders at different severity levels |
| **Request Validation** | Input sanitization → schema validation → business rules |

---

## Chain of Responsibility vs Decorator

| Aspect | Chain of Responsibility | Decorator |
|--------|------------------------|-----------|
| **Intent** | Find the right handler to process request | Add behavior to an object |
| **Flow** | Can stop at any point | Always goes through all layers |
| **Awareness** | Handlers are independent | Decorators wrap the same interface |
| **Result** | Only ONE handler typically processes | ALL decorators contribute |
| **Direction** | Unidirectional pass-along | Wrapping (before/after) |
| **Coupling** | Handlers don't know about each other | Each decorator knows its wrappee |

---

## Pros and Cons

### Pros
- **Single Responsibility** - Each handler focuses on one concern
- **Open/Closed** - New handlers added without modifying existing ones
- **Flexible composition** - Chain order changed at runtime
- **Reduced coupling** - Client doesn't know which handler processes the request
- **Fail-fast** - Invalid requests rejected early in the chain

### Cons
- **No guarantee of handling** - Request may reach end of chain unprocessed
- **Debugging difficulty** - Hard to trace which handler processed what
- **Performance** - Long chains add overhead for each request
- **Runtime errors** - Misconfigured chains only fail at runtime
- **Ordering sensitivity** - Wrong order can cause subtle bugs

---

## When to Use

- You have multiple processors for a request and don't know which should handle it ahead of time
- The processing order matters and should be configurable
- You want to decouple request senders from receivers
- You need a pipeline where each step can short-circuit

## When NOT to Use

- When every request must be handled (consider Observer or Command instead)
- When there's always exactly one known handler (just call it directly)
- When handler logic is trivial (over-engineering)
- When you need bidirectional communication between handlers
- When performance is critical and the chain is very long

---

## Running the Example

```bash
javac ChainOfResponsibilityPattern.java
java ChainOfResponsibilityPattern
```
