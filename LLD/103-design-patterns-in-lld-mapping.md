# Design Patterns in LLD: Complete Mapping Guide

## Quick Reference for Interviews: Which Pattern for Which Problem?

---

## 1. Problem -> Pattern Mapping Table

| # | LLD Problem | Primary Pattern(s) | Secondary Pattern(s) |
|---|-------------|-------------------|---------------------|
| 1 | Parking Lot | Strategy, Factory | Singleton, Observer |
| 2 | Elevator System | State, Strategy | Observer, Scheduler |
| 3 | Vending Machine | State, Chain of Responsibility | Strategy, Factory |
| 4 | ATM Machine | State, Chain of Responsibility | Strategy, Template Method |
| 5 | Traffic Signal | State, Observer | Mediator, Command |
| 6 | Snake & Ladder | State, Strategy | Factory, Observer |
| 7 | Tic-Tac-Toe | Strategy, State | Factory, Observer |
| 8 | Chess | Strategy, State | Factory, Command, Memento |
| 9 | Ludo | State, Observer | Strategy, Factory |
| 10 | Card Game (Blackjack) | Strategy, State | Factory, Iterator |
| 11 | Snakes Game | State, Observer | Strategy, Factory |
| 12 | Minesweeper | Strategy, Observer | State, Command |
| 13 | Sudoku Solver | Strategy, Backtracking | - |
| 14 | Tetris | State, Strategy | Observer, Command |
| 15 | 2048 Game | State, Command | Memento, Strategy |
| 16 | Library Management | Strategy, Observer | Factory, Decorator |
| 17 | Hotel Management | State, Strategy | Observer, Factory |
| 18 | Hospital Management | State, Observer | Strategy, Factory, Chain of Responsibility |
| 19 | Movie Ticket Booking | Strategy, Observer | State, Factory |
| 20 | Flight Booking | Strategy, Observer | State, Factory, Chain of Responsibility |
| 21 | Railway Reservation | Strategy, State | Observer, Factory |
| 22 | Restaurant Management | State, Observer | Strategy, Command |
| 23 | Food Delivery (Swiggy/Zomato) | Strategy, Observer | State, Factory, Proxy |
| 24 | Cab Booking (Uber/Ola) | Strategy, Observer | State, Factory, Proxy |
| 25 | Ride Sharing | Strategy, Observer | State, Factory |
| 26 | E-Commerce (Amazon) | Strategy, Observer | Factory, Decorator, Chain of Responsibility |
| 27 | Shopping Cart | Strategy, Decorator | Observer, Factory |
| 28 | Payment System | Strategy, Factory | Chain of Responsibility, Observer |
| 29 | Wallet System | State, Observer | Strategy, Command |
| 30 | Banking System | State, Strategy | Observer, Chain of Responsibility, Proxy |
| 31 | Stock Exchange | Observer, Strategy | Mediator, Command |
| 32 | Trading Platform | Observer, Strategy | Command, Memento, State |
| 33 | Auction System | Observer, State | Strategy, Command |
| 34 | Inventory Management | Observer, Strategy | Factory, State |
| 35 | Warehouse Management | Strategy, Observer | State, Factory, Command |
| 36 | Supply Chain | Chain of Responsibility, Observer | Strategy, State |
| 37 | File System | Composite, Iterator | Factory, Strategy |
| 38 | Text Editor | Command, Memento | Strategy, Observer, Composite |
| 39 | Spreadsheet (Excel) | Observer, Composite | Command, Memento, Strategy |
| 40 | IDE (Code Editor) | Command, Strategy | Observer, Composite, Factory |
| 41 | Version Control (Git) | Memento, Command | Composite, Strategy |
| 42 | Document Editor (Google Docs) | Command, Observer | Memento, Strategy, Mediator |
| 43 | Whiteboard (Collaborative) | Command, Memento | Observer, Strategy, Composite |
| 44 | Calendar System | Observer, Strategy | Factory, State |
| 45 | Task Manager (Trello/Jira) | State, Observer | Strategy, Command, Factory |
| 46 | Notification System | Observer, Strategy | Factory, Decorator, Chain of Responsibility |
| 47 | Email System | Strategy, Observer | Factory, Template Method, Chain of Responsibility |
| 48 | Chat System | Observer, Mediator | Strategy, Factory, Command |
| 49 | Social Media (Twitter) | Observer, Strategy | Factory, Decorator, Command |
| 50 | Social Network (Facebook) | Observer, Strategy | Factory, Proxy, Iterator |
| 51 | YouTube (Video Platform) | Observer, Strategy | Factory, Proxy, Decorator |
| 52 | Netflix (Streaming) | Strategy, Proxy | Observer, Factory, Decorator |
| 53 | Music Player (Spotify) | State, Strategy | Observer, Iterator, Command |
| 54 | Podcast Platform | Strategy, Observer | State, Factory, Iterator |
| 55 | Photo Sharing (Instagram) | Observer, Strategy | Factory, Decorator, Proxy |
| 56 | URL Shortener | Factory, Strategy | Proxy, Singleton |
| 57 | Paste Bin | Factory, Strategy | Proxy, Observer |
| 58 | Rate Limiter | Strategy, Chain of Responsibility | Decorator, Proxy |
| 59 | API Gateway | Chain of Responsibility, Proxy | Strategy, Factory, Decorator |
| 60 | Load Balancer | Strategy, Observer | Factory, Proxy |
| 61 | Cache System (LRU/LFU) | Strategy, Decorator | Observer, Proxy, Factory |
| 62 | Message Queue | Observer, Strategy | Factory, Command, Iterator |
| 63 | Pub-Sub System | Observer, Mediator | Strategy, Factory |
| 64 | Event Bus | Observer, Mediator | Strategy, Factory, Command |
| 65 | Task Scheduler | Strategy, Observer | Command, State, Priority Queue |
| 66 | Cron Job Scheduler | Strategy, Command | Observer, State, Factory |
| 67 | Thread Pool | Factory, Strategy | Observer, Command |
| 68 | Connection Pool | Factory, Singleton | Proxy, Strategy |
| 69 | Object Pool | Factory, Singleton | Proxy, Strategy |
| 70 | Logger System | Singleton, Chain of Responsibility | Strategy, Observer, Decorator |
| 71 | Configuration Manager | Singleton, Observer | Strategy, Proxy |
| 72 | Plugin System | Strategy, Factory | Observer, Decorator, Composite |
| 73 | Rule Engine | Strategy, Chain of Responsibility | Composite, Interpreter |
| 74 | Workflow Engine | State, Strategy | Command, Observer, Chain of Responsibility |
| 75 | Search Engine | Strategy, Iterator | Composite, Observer, Decorator |
| 76 | Recommendation Engine | Strategy, Observer | Factory, Decorator |
| 77 | Analytics Dashboard | Observer, Strategy | Composite, Decorator, Factory |
| 78 | Reporting System | Strategy, Template Method | Factory, Composite, Decorator |
| 79 | PDF Generator | Builder, Strategy | Factory, Template Method, Composite |
| 80 | Invoice Generator | Builder, Template Method | Strategy, Factory |
| 81 | Form Builder | Builder, Composite | Strategy, Observer, Factory |
| 82 | Quiz/Survey System | Builder, Strategy | State, Observer, Factory |
| 83 | Voting/Poll System | Observer, Strategy | State, Factory |
| 84 | Authentication System | Chain of Responsibility, Strategy | Factory, Proxy, Decorator |
| 85 | Authorization (RBAC) | Strategy, Chain of Responsibility | Composite, Proxy, Decorator |
| 86 | OAuth System | State, Strategy | Factory, Template Method |
| 87 | Multi-tenant System | Strategy, Factory | Proxy, Decorator, Abstract Factory |
| 88 | Feature Flag System | Strategy, Observer | Proxy, Factory, Decorator |
| 89 | A/B Testing | Strategy, Observer | Factory, Proxy |
| 90 | Circuit Breaker | State, Strategy | Proxy, Observer |
| 91 | Retry Mechanism | Strategy, Template Method | Proxy, Decorator |
| 92 | Saga Pattern (Distributed Tx) | State, Command | Observer, Strategy |
| 93 | CQRS Implementation | Strategy, Factory | Observer, Command |
| 94 | Event Sourcing | Command, Observer | Strategy, Factory, Memento |
| 95 | Unit Converter | Strategy, Factory | - |
| 96 | Currency Converter | Strategy, Factory | Observer, Proxy |
| 97 | Map/Navigation (Google Maps) | Strategy, Observer | Composite, Iterator, State |
| 98 | Ride Matching Algorithm | Strategy, Observer | Factory, State |
| 99 | Recommendation Feed | Strategy, Observer | Factory, Decorator, Iterator |
| 100 | Content Moderation | Chain of Responsibility, Strategy | Observer, Factory, State |

---

## 2. Pattern -> Problem Mapping (Reverse Lookup)

### Creational Patterns

#### Singleton
- Logger System (#70)
- Configuration Manager (#71)
- Connection Pool (#68)
- Object Pool (#69)
- URL Shortener (#56)
- Cache System (#61)

#### Factory Method / Abstract Factory
- Parking Lot (#1) - vehicle types
- Payment System (#28) - payment processors
- Notification System (#46) - notification channels
- E-Commerce (#26) - product types
- Multi-tenant System (#87) - tenant-specific instances
- Plugin System (#72) - plugin instantiation
- Thread Pool (#67) - thread creation
- Connection Pool (#68) - connection creation
- All booking systems - ticket/reservation creation

#### Builder
- PDF Generator (#79)
- Invoice Generator (#80)
- Form Builder (#81)
- Quiz/Survey System (#82)
- Complex query builders
- Report generators

#### Prototype
- Document Editor (#42) - copy/clone objects
- Spreadsheet (#39) - cell copying
- Whiteboard (#43) - shape duplication

---

### Structural Patterns

#### Adapter
- Payment System (#28) - third-party gateway adaptation
- Notification System (#46) - different provider APIs
- Multi-tenant System (#87) - database adapters

#### Decorator
- E-Commerce (#26) - pricing decorators (tax, discount, shipping)
- Shopping Cart (#27) - item modifiers
- Cache System (#61) - layered caching
- Rate Limiter (#58) - composed limits
- Notification System (#46) - enrichment layers
- Logger (#70) - log enrichment
- API Gateway (#59) - request/response modification

#### Proxy
- Netflix/YouTube (#51, #52) - lazy loading, access control
- Cache System (#61) - caching proxy
- API Gateway (#59) - protection proxy
- Rate Limiter (#58) - access control
- Social Network (#50) - lazy loading friend lists
- Banking System (#30) - security proxy

#### Composite
- File System (#37) - files and directories
- Form Builder (#81) - nested form groups
- Spreadsheet (#39) - cell ranges
- Rule Engine (#73) - composite rules
- Authorization (#85) - permission hierarchies
- Category/Menu trees in e-commerce

#### Facade
- E-Commerce (#26) - simplified order API
- Banking System (#30) - transaction facade
- Hotel Management (#17) - booking facade
- Any complex subsystem exposed via simple API

#### Bridge
- Notification System (#46) - notification type × channel
- Payment System (#28) - payment type × processor
- Reporting System (#78) - report type × format

#### Flyweight
- Text Editor (#38) - character formatting
- Chess (#8) - piece rendering
- Map/Navigation (#97) - map tiles

---

### Behavioral Patterns

#### Strategy
- **Pricing/Discount**: E-Commerce, Shopping Cart, Hotel, Flight
- **Sorting/Searching**: Search Engine, Recommendation
- **Routing/Allocation**: Load Balancer, Cab Booking, Ride Matching
- **Payment Processing**: Payment System, Wallet
- **Authentication**: Auth System, OAuth
- **Caching**: Cache System (LRU, LFU, FIFO)
- **Rate Limiting**: Rate Limiter (token bucket, sliding window, fixed window)
- **Scheduling**: Task Scheduler, Cron Jobs (FIFO, priority, round-robin)
- **Game AI**: Chess, Tic-Tac-Toe, Minesweeper

#### Observer
- **Real-time Updates**: Stock Exchange, Trading Platform, Auction
- **Notifications**: All notification-heavy systems
- **Chat/Social**: Chat System, Social Media, Social Network
- **Event-driven**: Event Bus, Pub-Sub, Message Queue
- **Monitoring**: Analytics Dashboard, Circuit Breaker
- **Collaborative**: Google Docs, Whiteboard, Spreadsheet
- **State Changes**: Inventory, Order Status, Booking Status

#### State
- **Finite State Machines**: Vending Machine, ATM, Elevator
- **Order Lifecycles**: E-Commerce orders, Food Delivery, Cab Booking
- **Game States**: Chess (check/checkmate), Card Games, Board Games
- **Connection States**: Circuit Breaker (closed/open/half-open)
- **Document States**: Task Manager (todo/in-progress/done)
- **Transaction States**: Banking, Wallet, Payment

#### Command
- **Undo/Redo**: Text Editor, Whiteboard, Spreadsheet, IDE
- **Queued Operations**: Message Queue, Task Scheduler
- **Transactional**: Banking (debit/credit), Trading (buy/sell)
- **Macro Recording**: IDE, Spreadsheet
- **Event Sourcing**: Any audit-trail system

#### Chain of Responsibility
- **Validation Pipelines**: Auth, Form validation, API Gateway
- **Request Processing**: ATM (dispense), Logger (log levels)
- **Approval Workflows**: Leave management, Expense approval
- **Filter Chains**: Content Moderation, Spam detection
- **Middleware**: API Gateway, Rate Limiter

#### Mediator
- **Chat Rooms**: Chat System (#48)
- **Air Traffic Control**: Analogous to request routing
- **Event Coordination**: Event Bus (#64), Pub-Sub (#63)
- **UI Components**: Complex form interactions
- **Stock Exchange**: Buyer-seller matching (#31)

#### Iterator
- **Collection Traversal**: File System, Social Network feeds
- **Pagination**: Search results, Recommendation feed
- **Playlist**: Music Player, Video Platform
- **Tree Traversal**: Category trees, File systems

#### Memento
- **Undo/Redo**: Text Editor, Whiteboard, IDE
- **Snapshots**: Version Control (Git), Game saves
- **Checkpoints**: Workflow Engine, Long-running transactions
- **Drafts**: Document Editor, Email drafts

#### Template Method
- **Report Generation**: Reporting System, Invoice Generator
- **Data Processing**: ETL pipelines, Import/Export
- **Game Loops**: Board games turn sequence
- **Authentication Flows**: OAuth, Social login
- **Retry Logic**: Retry Mechanism

#### Interpreter
- **Rule Engines**: Rule Engine (#73)
- **Query Languages**: Search filters, Custom DSLs
- **Expression Evaluation**: Spreadsheet formulas
- **Validation Rules**: Complex business rules

#### Visitor
- **Tax Calculation**: E-Commerce (different tax rules per item type)
- **Export Formats**: Document export (PDF, HTML, Word)
- **Code Analysis**: IDE (linting, metrics)
- **File System Operations**: Virus scan, size calculation

---

## 3. Interview Decision Framework

### "How to Pick the Right Pattern" - Decision Flowchart

```
START: What is the core problem?
│
├─ Objects change behavior based on internal state?
│  └─ USE: State Pattern
│     Examples: Vending Machine, ATM, Order Status, Circuit Breaker
│
├─ Need to swap algorithms/behaviors at runtime?
│  └─ USE: Strategy Pattern
│     Examples: Payment methods, Sorting, Pricing, Routing
│
├─ Objects need to be notified of changes?
│  └─ USE: Observer Pattern
│     Examples: Stock prices, Notifications, Real-time updates
│
├─ Need undo/redo or transaction logging?
│  └─ USE: Command + Memento
│     Examples: Text Editor, Whiteboard, Version Control
│
├─ Request passes through multiple handlers?
│  └─ USE: Chain of Responsibility
│     Examples: Auth middleware, Validation, ATM dispense
│
├─ Complex object creation with many optional parts?
│  └─ USE: Builder Pattern
│     Examples: PDF, Invoice, Form, Query builders
│
├─ Tree/hierarchical structure?
│  └─ USE: Composite Pattern
│     Examples: File System, Menu, Organization hierarchy
│
├─ Need to add behavior without modifying existing code?
│  └─ USE: Decorator Pattern
│     Examples: Pizza toppings, Notification enrichment, Logging
│
├─ Need single global instance?
│  └─ USE: Singleton (carefully!)
│     Examples: Logger, Config, Connection Pool
│
├─ Multiple related objects need creation?
│  └─ USE: Factory / Abstract Factory
│     Examples: UI themes, Cross-platform, Vehicle types
│
├─ Need to control access or add indirection?
│  └─ USE: Proxy Pattern
│     Examples: Lazy loading, Access control, Caching
│
├─ Many-to-many communication between objects?
│  └─ USE: Mediator Pattern
│     Examples: Chat room, Air traffic control, UI components
│
└─ Need to define a skeleton algorithm with varying steps?
   └─ USE: Template Method
      Examples: Report generation, Game loops, Data processing
```

### Quick Decision Matrix

| If you see... | Think... |
|---------------|----------|
| "multiple types of X" | Strategy or Factory |
| "states: pending, active, closed..." | State Pattern |
| "notify when X changes" | Observer |
| "undo/redo" | Command + Memento |
| "validate → process → log" | Chain of Responsibility |
| "files/folders" or "part-whole" | Composite |
| "add features dynamically" | Decorator |
| "one instance globally" | Singleton |
| "complex construction" | Builder |
| "different but related families" | Abstract Factory |
| "control access to X" | Proxy |
| "reduce coupling between many objects" | Mediator |
| "traverse without exposing internals" | Iterator |
| "save and restore state" | Memento |
| "same operation on different types" | Visitor |

---

## 4. Common Mistakes in Applying Patterns

### Mistake 1: State vs Strategy Confusion
```
WRONG: Using Strategy when object has lifecycle states
RIGHT: Use State when behavior changes based on INTERNAL state transitions
       Use Strategy when behavior is INJECTED from outside

Key Difference:
- State: Object transitions itself (vending machine: idle → dispensing → done)
- Strategy: Caller picks the algorithm (sort: quicksort vs mergesort)
```

### Mistake 2: Observer Overuse
```
WRONG: Making everything observable "just in case"
RIGHT: Only use Observer when:
  - Multiple dependents need updates
  - Publishers shouldn't know about subscribers
  - The relationship is truly one-to-many

Anti-pattern: Two objects directly communicating via Observer
Better: Direct method call or simple callback
```

### Mistake 3: Singleton Abuse
```
WRONG: Making everything Singleton for "convenience"
RIGHT: Only use Singleton when:
  - Exactly ONE instance must exist (not "should" but "must")
  - Global access point is genuinely needed
  - Instance is stateless or thread-safe

Better alternatives: Dependency Injection, Factory
```

### Mistake 4: Factory When Not Needed
```
WRONG: Factory for a single concrete class
RIGHT: Use Factory when:
  - Multiple concrete implementations exist
  - Creation logic is complex
  - Client shouldn't know concrete types

If there's only one implementation, just use `new`. YAGNI.
```

### Mistake 5: Command Pattern Overhead
```
WRONG: Wrapping every method call in a Command
RIGHT: Use Command only when you need:
  - Undo/Redo capability
  - Queuing/scheduling operations
  - Logging/auditing every operation
  - Macro recording

Simple CRUD? Just call the method directly.
```

### Mistake 6: Decorator vs Inheritance
```
WRONG: Deep inheritance hierarchies (CheesePizzaWithOlives extends CheesePizza)
RIGHT: Use Decorator for combinatorial feature addition

WRONG: Using Decorator when you only have 2-3 fixed variants
RIGHT: Simple inheritance is fine for small, fixed hierarchies
```

### Mistake 7: Composite When Flat is Fine
```
WRONG: Composite pattern for a flat list of items
RIGHT: Use Composite only when:
  - You have genuine tree/hierarchical structure
  - Leaf and composite nodes share operations
  - Depth is variable/unknown

A shopping cart with items? Just use a List. Not everything is a tree.
```

### Mistake 8: Chain of Responsibility vs Simple If-Else
```
WRONG: CoR for 2-3 fixed conditions
RIGHT: Use CoR when:
  - Handlers are dynamically configurable
  - The chain may grow/shrink at runtime
  - Handlers are independently developed/deployed

3 validation checks? If-else is perfectly fine.
```

---

## 5. Pattern Combinations That Frequently Appear Together

### Combination 1: State + Strategy
**When**: Object has lifecycle states AND different algorithms within states

```
Problems: Vending Machine, ATM, Elevator, Order Management

Example - Vending Machine:
- State: Idle → HasMoney → Dispensing → Done
- Strategy: PaymentStrategy (cash, card, UPI) used in HasMoney state

Example - ATM:
- State: Idle → CardInserted → Authenticated → Transaction → Done  
- Strategy: TransactionStrategy (withdraw, deposit, transfer)
- Chain of Responsibility: Dispense (₹500 → ₹200 → ₹100)
```

### Combination 2: Strategy + Observer
**When**: Different algorithms produce results that others need to know about

```
Problems: Payment System, Pricing Engine, Stock Trading, Recommendation

Example - Payment System:
- Strategy: PaymentGateway (Stripe, PayPal, RazorPay)
- Observer: OrderService, InventoryService, NotificationService
  observe payment status changes

Example - Dynamic Pricing:
- Strategy: PricingAlgorithm (surge, discount, loyalty)
- Observer: UI, Analytics, Competitors observe price changes
```

### Combination 3: Command + Memento
**When**: Need to execute operations AND undo them by restoring state

```
Problems: Text Editor, Whiteboard, Spreadsheet, IDE, Version Control

Example - Text Editor:
- Command: InsertCommand, DeleteCommand, FormatCommand
- Memento: Snapshot of document state before each command
- Command.execute() → save Memento → perform action
- Command.undo() → restore from Memento

Example - Collaborative Whiteboard:
- Command: DrawCommand, MoveCommand, ResizeCommand
- Memento: Canvas state snapshots
- Observer: Other users get notified of changes
```

### Combination 4: Chain of Responsibility + Strategy
**When**: Pipeline of processors where each processor has swappable algorithms

```
Problems: Validation, API Gateway, Content Moderation, Auth pipelines

Example - API Gateway:
- Chain: AuthHandler → RateLimitHandler → CacheHandler → RouterHandler
- Strategy within each handler:
  - AuthHandler uses AuthStrategy (JWT, OAuth, API Key)
  - RateLimitHandler uses RateLimitStrategy (Token Bucket, Sliding Window)
  - CacheHandler uses CacheStrategy (LRU, LFU, TTL)

Example - Content Moderation:
- Chain: ProfanityFilter → SpamDetector → ImageAnalyzer → ManualReview
- Strategy: Each filter can use different algorithms (ML, regex, blocklist)
```

### Combination 5: Composite + Iterator
**When**: Tree structure that needs to be traversed in multiple ways

```
Problems: File System, Category Trees, Organization Hierarchy, Menu

Example - File System:
- Composite: File and Directory share FileSystemNode interface
- Iterator: BreadthFirstIterator, DepthFirstIterator, FilteredIterator
- Visitor: SizeCalculator, SearchVisitor, PermissionChecker

Example - E-Commerce Categories:
- Composite: Category contains sub-categories and products
- Iterator: Traverse for display, search, breadcrumb generation
```

### Combination 6: Factory + Strategy
**When**: Multiple implementations exist AND need to be created dynamically

```
Problems: Payment, Notification, Authentication, Export, Reporting

Example - Notification System:
- Factory: NotificationFactory.create("email") → EmailNotification
- Strategy: DeliveryStrategy (immediate, batched, scheduled)
- Decorator: Add tracking, retry, formatting

Example - Report Generator:
- Factory: ReportFactory.create("sales") → SalesReport
- Strategy: FormatStrategy (PDF, Excel, HTML)
- Template Method: Report generation skeleton
```

### Combination 7: Observer + Mediator
**When**: Many-to-many communication with complex coordination logic

```
Problems: Chat System, Stock Exchange, Event Bus, Game Lobbies

Example - Chat System:
- Mediator: ChatRoom coordinates messages between users
- Observer: Users subscribe to room events (join, leave, typing)
- Command: SendMessage, EditMessage, DeleteMessage

Example - Stock Exchange:
- Mediator: MatchingEngine coordinates buyers and sellers
- Observer: Traders observe price changes
- Strategy: MatchingStrategy (price-time priority, pro-rata)
```

### Combination 8: State + Observer
**When**: State transitions trigger notifications to interested parties

```
Problems: Order Management, Task Tracking, Workflow Engines

Example - Food Delivery Order:
- State: Placed → Confirmed → Preparing → OutForDelivery → Delivered
- Observer: Customer, Restaurant, Driver, Analytics
  all observe state transitions
- Each transition triggers different notifications to different observers
```

### Combination 9: Proxy + Decorator
**When**: Need both access control AND dynamic feature addition

```
Problems: API Gateway, Cache with Auth, Protected Resources

Example - API Gateway:
- Proxy: AuthProxy controls access (authentication check)
- Decorator: LoggingDecorator, MetricsDecorator, CompressionDecorator
- Chain of Responsibility: Pipeline of processing steps

Distinction:
- Proxy: Controls ACCESS (same interface, different purpose)
- Decorator: Adds BEHAVIOR (same interface, enhanced functionality)
```

### Combination 10: Builder + Composite
**When**: Building complex tree structures step by step

```
Problems: Form Builder, Query Builder, UI Layout Builder, Document Builder

Example - Form Builder:
- Builder: FormBuilder.addSection().addField().addValidation().build()
- Composite: Form → Section → FieldGroup → Field (tree structure)
- Strategy: ValidationStrategy per field
- Observer: Form watches fields for changes
```

---

## 6. Red Flags in Interviews - Over-Engineering & Anti-Patterns

### Red Flag 1: Pattern for Pattern's Sake
```
BAD: "I'll use Abstract Factory here because it's a creational pattern"
GOOD: "I need Abstract Factory because we have multiple families of 
       related objects (iOS vs Android UI components)"

Rule: Name the PROBLEM first, then the pattern. Never the reverse.
```

### Red Flag 2: Using All 23 GoF Patterns
```
BAD: Trying to shoehorn every pattern into one design
GOOD: Most LLD problems need 2-4 patterns maximum

Typical distribution for a 45-min interview:
- 1 primary structural pattern
- 1-2 behavioral patterns  
- 1 creational pattern (usually Factory)
```

### Red Flag 3: Over-abstracting Simple Things
```
BAD: StrategyFactory that creates a Strategy that executes a Command
     that gets processed by a Chain that notifies an Observer
GOOD: Direct, clear code with patterns only where they solve real problems

Ask yourself: "Would a new developer understand this in 5 minutes?"
```

### Red Flag 4: Premature Generalization
```
BAD: "Let me make this extensible for 50 payment gateways"
     when the requirement mentions only 2-3
GOOD: Design for current requirements + reasonable extension

YAGNI: You Ain't Gonna Need It
Design for 2-3x growth, not 100x.
```

### Red Flag 5: Ignoring SOLID While Using Patterns
```
BAD: God class that implements 5 patterns internally
GOOD: Each pattern participant is a focused, single-responsibility class

Patterns should SUPPORT SOLID, not replace it:
- S: Each class has one reason to change
- O: Extend via Strategy/Decorator, not modification
- L: Subtypes are substitutable
- I: Small, focused interfaces
- D: Depend on abstractions (Strategy interface, not concrete)
```

### Red Flag 6: Not Justifying Pattern Choices
```
BAD: "I'll use Observer here" (no explanation)
GOOD: "I'll use Observer because:
  1. Multiple services need to react to order status changes
  2. The order service shouldn't know about all dependents
  3. New listeners may be added without modifying order logic"

Always state WHY with 2-3 concrete reasons.
```

### Red Flag 7: Mixing Up Similar Patterns
```
Common confusions:
- Strategy vs State: External algorithm swap vs internal state transition
- Decorator vs Proxy: Add behavior vs control access
- Factory vs Builder: Create variants vs construct complex objects
- Observer vs Mediator: Broadcast vs coordinate
- Command vs Strategy: Encapsulate request vs encapsulate algorithm
- Template Method vs Strategy: Inheritance-based vs composition-based

In interview: Explicitly state the distinction if you use either of a pair.
```

### Red Flag 8: Not Considering Thread Safety
```
BAD: Singleton without synchronization in concurrent system
GOOD: "This Singleton uses double-checked locking because multiple 
       threads access it during initialization"

Patterns affected by concurrency:
- Singleton: Thread-safe creation
- Observer: Thread-safe notification dispatch
- State: Atomic state transitions
- Command Queue: Thread-safe enqueue/dequeue
- Object Pool: Synchronized checkout/return
```

---

## 7. Interview Quick-Fire: Pattern Selection Cheat Sheet

### Given These Requirements, Use This Pattern:

| Requirement Phrase | Pattern |
|-------------------|---------|
| "multiple payment methods" | Strategy |
| "order goes through stages" | State |
| "notify users in real-time" | Observer |
| "undo last action" | Command + Memento |
| "validate request before processing" | Chain of Responsibility |
| "files and folders" | Composite |
| "add toppings to pizza" | Decorator |
| "create objects without specifying class" | Factory |
| "build complex report step by step" | Builder |
| "only one database connection" | Singleton |
| "lazy load heavy object" | Proxy |
| "chat room with multiple users" | Mediator |
| "iterate over playlist" | Iterator |
| "save game progress" | Memento |
| "calculate tax differently per country" | Visitor/Strategy |
| "parse expressions/rules" | Interpreter |
| "algorithm skeleton with varying steps" | Template Method |
| "adapt third-party API" | Adapter |
| "different UI for different platforms" | Abstract Factory + Bridge |

---

## 8. Minimal Pattern Implementation Signatures

### For Quick Interview Whiteboarding:

```java
// Strategy
interface Strategy { Result execute(Input input); }
class Context { private Strategy strategy; void setStrategy(Strategy s); }

// State  
interface State { void handle(Context ctx); }
class Context { private State state; void setState(State s); void request(); }

// Observer
interface Observer { void update(Event event); }
class Subject { List<Observer> observers; void notify(Event e); }

// Command
interface Command { void execute(); void undo(); }
class Invoker { Stack<Command> history; void executeCommand(Command c); }

// Chain of Responsibility
abstract class Handler { Handler next; abstract boolean handle(Request r); }

// Factory
interface Factory { Product create(String type); }

// Decorator
class Decorator implements Component { Component wrapped; }

// Composite
interface Node { void operation(); }
class Composite implements Node { List<Node> children; }

// Builder
class Builder { Builder setX(); Builder setY(); Product build(); }
```

---

## Summary: Top 5 Patterns by Interview Frequency

1. **Strategy** - Used in 80%+ of LLD problems (algorithms, behaviors, policies)
2. **Observer** - Used in 60%+ (notifications, real-time, event-driven)
3. **State** - Used in 40%+ (lifecycle management, FSMs)
4. **Factory** - Used in 50%+ (object creation, type management)
5. **Command** - Used in 25%+ (undo/redo, queuing, audit trails)

Master these five thoroughly. The rest are situational but knowing when to reach for them distinguishes good from great candidates.
