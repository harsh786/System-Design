# Design an Object-Oriented Design Interview Approach

## Complete LLD Interview Framework & Strategy Guide

---

## 1. LLD Interview Framework (Step-by-Step)

### Step 1: Clarify Requirements (2 minutes)

**Goal:** Narrow scope, identify constraints, show structured thinking.

#### Universal Questions to Ask:
```
1. What are the core use cases? (Pick top 3-5)
2. Who are the actors/users of the system?
3. What is the scale? (Single machine vs distributed)
4. Do we need concurrency/thread-safety?
5. Are there any specific design patterns you'd like me to use?
6. Should I focus on extensibility or simplicity?
7. What are the constraints? (Memory, time, real-time?)
```

#### Requirement Documentation Template:
```
Functional Requirements:
- FR1: ...
- FR2: ...
- FR3: ...

Non-Functional Requirements:
- NFR1: Thread-safety needed? Y/N
- NFR2: Scale expectations
- NFR3: Latency requirements

Actors:
- Actor1: ...
- Actor2: ...

Core Use Cases:
- UC1: ...
- UC2: ...
- UC3: ...
```

**Pro Tip:** Write requirements on the whiteboard/shared doc. This gives you a checklist to verify your design against at the end.

---

### Step 2: Identify Core Objects/Entities (3 minutes)

**Technique: Noun Extraction**

Read through the requirements and extract all nouns — these become candidate classes.

```
Example: "A parking lot has multiple floors. Each floor has parking spots
of different sizes. Vehicles enter through entry panels and exit
through exit panels. Payment can be made at exit or at info kiosks."

Nouns extracted:
- ParkingLot
- Floor
- ParkingSpot (+ sizes → enum SpotSize)
- Vehicle (+ types → enum VehicleType)
- EntryPanel
- ExitPanel
- Payment
- Ticket
- InfoKiosk
```

#### Entity Classification:
| Category | Examples |
|----------|----------|
| **Core Domain Objects** | ParkingSpot, Vehicle, Ticket |
| **Actors/Users** | Customer, Admin, Driver |
| **Services/Managers** | ParkingService, PaymentProcessor |
| **Enumerations** | Status, Type, Size |
| **Value Objects** | Address, Money, DateRange |
| **Events** | PaymentEvent, NotificationEvent |

---

### Step 3: Establish Relationships (2 minutes)

#### Three Relationship Types:

| Relationship | Keyword | UML | Example |
|-------------|---------|-----|---------|
| **IS-A** (Inheritance) | "is a type of" | Solid line + hollow triangle | Car IS-A Vehicle |
| **HAS-A** (Composition) | "owns, contains" | Solid diamond | ParkingLot HAS Floors |
| **USES-A** (Dependency) | "uses, interacts with" | Dashed arrow | ParkingService USES PaymentProcessor |

#### Composition vs Aggregation:
```
Composition (strong ownership - child dies with parent):
  - ParkingLot ◆── Floor (floors don't exist without lot)
  - Order ◆── OrderItem

Aggregation (weak ownership - child can exist independently):
  - Department ◇── Employee (employee exists without dept)
  - Playlist ◇── Song
```

#### Quick Relationship Matrix:
```
             ParkingLot  Floor  Spot  Vehicle  Ticket
ParkingLot       -        has    -      -        -
Floor            -         -    has     -        -
Spot             -         -     -    holds      -
Vehicle          -         -     -      -      has
Ticket           -         -   refs    refs      -
```

---

### Step 4: Define Key Interfaces & Abstract Classes (5 minutes)

#### When to use Interface vs Abstract Class:

| Use Interface When | Use Abstract Class When |
|-------------------|------------------------|
| Multiple unrelated classes share behavior | Classes share common code |
| You want to define a contract | You want partial implementation |
| You need multiple inheritance | You have a clear hierarchy |
| Behavior can be "plugged in" | You need constructors/fields |

#### Common Interface Patterns in LLD:

```java
// Strategy Pattern - Payment processing
interface PaymentStrategy {
    PaymentResult pay(Money amount);
    void refund(String transactionId);
}

// Observer Pattern - Notifications
interface Observer {
    void update(Event event);
}

interface Observable {
    void addObserver(Observer o);
    void removeObserver(Observer o);
    void notifyObservers(Event event);
}

// Command Pattern - Actions
interface Command {
    void execute();
    void undo();
}

// Factory Pattern - Object creation
interface VehicleFactory {
    Vehicle createVehicle(VehicleType type);
}
```

#### Abstract Class Example:
```java
abstract class Vehicle {
    private String licensePlate;
    private VehicleType type;

    public Vehicle(String licensePlate, VehicleType type) {
        this.licensePlate = licensePlate;
        this.type = type;
    }

    // Template Method
    public abstract SpotSize getRequiredSpotSize();

    // Concrete method shared by all
    public String getLicensePlate() {
        return licensePlate;
    }
}

class Car extends Vehicle {
    public Car(String licensePlate) {
        super(licensePlate, VehicleType.CAR);
    }

    @Override
    public SpotSize getRequiredSpotSize() {
        return SpotSize.MEDIUM;
    }
}
```

---

### Step 5: Apply Design Patterns (5 minutes)

#### Pattern Selection Guide:

| Problem | Pattern | When to Apply |
|---------|---------|---------------|
| Object creation complexity | **Factory / Abstract Factory** | Multiple types of similar objects |
| Only one instance needed | **Singleton** | Database, Cache, Config |
| Need to notify multiple objects | **Observer** | Event systems, notifications |
| Multiple algorithms, choose at runtime | **Strategy** | Payment, sorting, pricing |
| Step-by-step construction | **Builder** | Complex object with many params |
| Add behavior dynamically | **Decorator** | Toppings, features, middleware |
| Simplify complex subsystem | **Facade** | Service layer over complex logic |
| Undo/redo, queuing | **Command** | Game moves, transactions |
| State-dependent behavior | **State** | Vending machine, order status |
| Iterate without exposing internals | **Iterator** | Collections, streams |
| Define skeleton, let subclass fill | **Template Method** | Game turns, document processing |
| Chain of responsibility | **Chain of Responsibility** | Middleware, approval workflows |

#### Top 5 Patterns for LLD Interviews:

**1. Strategy Pattern** (Most frequently applicable)
```java
interface PricingStrategy {
    double calculatePrice(Ride ride);
}

class SurgePricing implements PricingStrategy {
    private double multiplier;
    public double calculatePrice(Ride ride) {
        return ride.getBasePrice() * multiplier;
    }
}

class FlatPricing implements PricingStrategy {
    public double calculatePrice(Ride ride) {
        return ride.getBasePrice();
    }
}
```

**2. Observer Pattern**
```java
interface EventListener {
    void onEvent(Event event);
}

class NotificationService implements EventListener {
    public void onEvent(Event event) {
        // Send notification
    }
}

class EventBus {
    private Map<EventType, List<EventListener>> listeners = new HashMap<>();

    public void subscribe(EventType type, EventListener listener) {
        listeners.computeIfAbsent(type, k -> new ArrayList<>()).add(listener);
    }

    public void publish(Event event) {
        listeners.getOrDefault(event.getType(), Collections.emptyList())
                 .forEach(l -> l.onEvent(event));
    }
}
```

**3. Factory Pattern**
```java
class VehicleFactory {
    public static Vehicle create(VehicleType type, String plate) {
        switch (type) {
            case CAR: return new Car(plate);
            case TRUCK: return new Truck(plate);
            case MOTORCYCLE: return new Motorcycle(plate);
            default: throw new IllegalArgumentException("Unknown type");
        }
    }
}
```

**4. State Pattern**
```java
interface VendingMachineState {
    void insertCoin(VendingMachine machine, Coin coin);
    void selectProduct(VendingMachine machine, Product product);
    void dispense(VendingMachine machine);
}

class IdleState implements VendingMachineState {
    public void insertCoin(VendingMachine machine, Coin coin) {
        machine.addBalance(coin.getValue());
        machine.setState(new HasMoneyState());
    }
    public void selectProduct(VendingMachine m, Product p) {
        throw new IllegalStateException("Insert coin first");
    }
    public void dispense(VendingMachine m) {
        throw new IllegalStateException("Insert coin first");
    }
}
```

**5. Singleton Pattern**
```java
class ParkingLotManager {
    private static volatile ParkingLotManager instance;

    private ParkingLotManager() {}

    public static ParkingLotManager getInstance() {
        if (instance == null) {
            synchronized (ParkingLotManager.class) {
                if (instance == null) {
                    instance = new ParkingLotManager();
                }
            }
        }
        return instance;
    }
}
```

---

### Step 6: Write Code (15 minutes)

#### Order of Implementation:

```
1. Enums (1 min)           → Quick wins, sets context
2. Interfaces (2 min)      → Shows design thinking
3. Core Models (4 min)     → Domain objects
4. Service/Manager (5 min) → Business logic
5. Demo/Usage (3 min)      → Prove it works
```

#### Code Template:

```java
// ============ STEP 1: Enums ============
enum SpotType { SMALL, MEDIUM, LARGE, HANDICAPPED }
enum VehicleType { MOTORCYCLE, CAR, TRUCK }
enum TicketStatus { ACTIVE, PAID, LOST }

// ============ STEP 2: Interfaces ============
interface ParkingStrategy {
    ParkingSpot findSpot(Vehicle vehicle, List<ParkingFloor> floors);
}

interface PaymentProcessor {
    Receipt processPayment(Ticket ticket, PaymentMethod method);
}

// ============ STEP 3: Core Models ============
class ParkingSpot {
    private final String id;
    private final SpotType type;
    private Vehicle currentVehicle;
    private boolean isAvailable;

    public ParkingSpot(String id, SpotType type) {
        this.id = id;
        this.type = type;
        this.isAvailable = true;
    }

    public synchronized boolean assignVehicle(Vehicle vehicle) {
        if (!isAvailable) return false;
        this.currentVehicle = vehicle;
        this.isAvailable = false;
        return true;
    }

    public synchronized void freeSpot() {
        this.currentVehicle = null;
        this.isAvailable = true;
    }
}

class Ticket {
    private final String id;
    private final Vehicle vehicle;
    private final ParkingSpot spot;
    private final LocalDateTime entryTime;
    private LocalDateTime exitTime;
    private TicketStatus status;

    public Ticket(Vehicle vehicle, ParkingSpot spot) {
        this.id = UUID.randomUUID().toString();
        this.vehicle = vehicle;
        this.spot = spot;
        this.entryTime = LocalDateTime.now();
        this.status = TicketStatus.ACTIVE;
    }
}

// ============ STEP 4: Service Layer ============
class ParkingLotService {
    private final List<ParkingFloor> floors;
    private final ParkingStrategy parkingStrategy;
    private final Map<String, Ticket> activeTickets;

    public ParkingLotService(List<ParkingFloor> floors, ParkingStrategy strategy) {
        this.floors = floors;
        this.parkingStrategy = strategy;
        this.activeTickets = new ConcurrentHashMap<>();
    }

    public Ticket parkVehicle(Vehicle vehicle) {
        ParkingSpot spot = parkingStrategy.findSpot(vehicle, floors);
        if (spot == null) throw new ParkingFullException("No spot available");

        spot.assignVehicle(vehicle);
        Ticket ticket = new Ticket(vehicle, spot);
        activeTickets.put(ticket.getId(), ticket);
        return ticket;
    }

    public Receipt exitVehicle(String ticketId, PaymentMethod method) {
        Ticket ticket = activeTickets.get(ticketId);
        if (ticket == null) throw new InvalidTicketException("Ticket not found");

        ticket.markExit();
        ticket.getSpot().freeSpot();
        activeTickets.remove(ticketId);

        return paymentProcessor.processPayment(ticket, method);
    }
}

// ============ STEP 5: Usage Demo ============
// ParkingLotService service = new ParkingLotService(floors, new NearestSpotStrategy());
// Ticket ticket = service.parkVehicle(new Car("ABC-123"));
// Receipt receipt = service.exitVehicle(ticket.getId(), PaymentMethod.CARD);
```

---

### Step 7: Discuss Extensibility & Trade-offs (3 minutes)

#### Extensibility Talking Points:
```
"My design supports extension through..."
1. New vehicle types → just extend Vehicle class
2. New payment methods → implement PaymentProcessor interface
3. New pricing strategies → implement PricingStrategy
4. New spot allocation algorithms → implement ParkingStrategy
5. Event-driven features → subscribe to EventBus

"Following SOLID principles..."
- S: Each class has one responsibility
- O: Open for extension (new strategies) closed for modification
- L: Subtypes substitutable (Car/Truck as Vehicle)
- I: Small, focused interfaces
- D: Service depends on abstractions (ParkingStrategy interface)
```

#### Trade-offs to Discuss:
| Decision | Pro | Con |
|----------|-----|-----|
| Strategy over if-else | Extensible, testable | More classes |
| Singleton for manager | Global access | Hard to test |
| Observer for events | Decoupled | Debugging harder |
| Composition over inheritance | Flexible | More boilerplate |
| ConcurrentHashMap | Thread-safe | Slight perf cost |

---

## 2. UML Diagram Quick Guide

### Class Diagram Notation:

```
┌─────────────────────────────┐
│        <<interface>>         │   ← Stereotype
│       PaymentStrategy        │   ← Interface name
├─────────────────────────────┤
│                             │   ← No fields for interface
├─────────────────────────────┤
│ + pay(amount: Money): Result│   ← Methods
│ + refund(id: String): void  │
└─────────────────────────────┘

┌─────────────────────────────┐
│         Vehicle              │   ← Class name (italic = abstract)
├─────────────────────────────┤
│ - licensePlate: String       │   ← Private field
│ # type: VehicleType          │   ← Protected field
│ + status: Status             │   ← Public field
├─────────────────────────────┤
│ + getLicensePlate(): String  │   ← Public method
│ # calculateFee(): double     │   ← Protected method
│ - validate(): boolean        │   ← Private method
└─────────────────────────────┘
```

### Visibility Modifiers:
```
+ Public
- Private
# Protected
~ Package-private (default)
```

### Relationship Notation:

```
INHERITANCE (IS-A):
  Child ────────▷ Parent          (solid line + hollow triangle)
  Car ────────▷ Vehicle

INTERFACE IMPLEMENTATION:
  Class - - - -▷ Interface        (dashed line + hollow triangle)
  CreditCard - - -▷ PaymentStrategy

COMPOSITION (strong HAS-A, lifecycle dependent):
  Whole ◆──────── Part            (solid diamond)
  ParkingLot ◆── Floor

AGGREGATION (weak HAS-A, independent lifecycle):
  Whole ◇──────── Part            (hollow diamond)
  Department ◇── Employee

ASSOCIATION (general relationship):
  ClassA ──────── ClassB          (solid line)
  Student ──── Course

DEPENDENCY (uses temporarily):
  Client - - - -> Supplier        (dashed arrow)
  Service - - -> Logger
```

### Multiplicity Notation:
```
1       → Exactly one
0..1    → Zero or one (optional)
*       → Zero or more
1..*    → One or more
n       → Exactly n
0..n    → Zero to n
```

### Example UML (Text-based):
```
┌────────────┐         ┌──────────────┐
│ ParkingLot │◆────────│    Floor     │
│            │  1   *  │             │
└────────────┘         └──────┬───────┘
                              │ 1
                              │
                              │ *
                       ┌──────┴───────┐
                       │ ParkingSpot  │
                       │              │◇───── Vehicle
                       └──────────────┘ 0..1
```

---

## 3. Common Clarifying Questions by Problem Type

### For System Problems (Parking Lot, ATM, Elevator, Vending Machine)

```
1. How many [units]? (floors, ATMs, elevators)
2. What types/sizes exist? (spot sizes, bill denominations)
3. Is it multi-threaded? (concurrent access)
4. What are the states? (idle, processing, error)
5. What happens on failure? (out of cash, full lot)
6. Is there a rate/pricing model?
7. Do we need logging/audit trail?
8. Real-time display/monitoring needed?
9. Priority or scheduling algorithm?
10. Admin operations needed? (refill, maintenance)
```

### For Game Problems (Chess, Tic-Tac-Toe, Snakes & Ladders, Card Games)

```
1. How many players? (2, multiplayer, AI?)
2. What are the rules? (standard or custom?)
3. Turn-based or real-time?
4. How do we determine winner?
5. Can moves be undone?
6. Timer/time-limit per move?
7. Save/load game state?
8. Spectator mode?
9. What constitutes an invalid move?
10. Are there special rules? (castling, en passant)
```

### For Data Structure Problems (LRU Cache, HashMap, BlockingQueue)

```
1. What operations are needed? (get, put, delete)
2. Thread-safe? Concurrent access?
3. What is the capacity/size limit?
4. Eviction policy? (LRU, LFU, FIFO)
5. What are key/value types? (generic?)
6. Time complexity requirements?
7. Null keys/values allowed?
8. Resizing behavior?
9. Iterator support? (fail-fast?)
10. Expiration/TTL support?
```

### For Platform Problems (Splitwise, BookMyShow, Uber, Amazon)

```
1. Who are the actors? (buyer, seller, driver, admin)
2. What are the core flows? (book, pay, cancel)
3. How is pricing done? (fixed, dynamic, surge)
4. Notification requirements?
5. Payment splitting logic?
6. Concurrency? (double booking, race conditions)
7. Search/filter requirements?
8. Rating/review system?
9. Cancellation/refund policy?
10. Geographic scope? (single city, multi-city)
```

---

## 4. Code Organization in Interview

### What to Write FIRST (High Impact):

```
Priority 1 - Enums & Constants (30 seconds)
  → Shows you understand the domain vocabulary
  → enum Status { ACTIVE, INACTIVE, BLOCKED }
  → enum Type { REGULAR, PREMIUM, VIP }

Priority 2 - Core Interfaces (1-2 minutes)
  → Shows design thinking and abstraction
  → interface PaymentStrategy { ... }
  → interface Observer { ... }

Priority 3 - Domain Models (3-4 minutes)
  → Core entities with key fields and methods
  → Focus on the 2-3 most important classes

Priority 4 - Service/Manager Class (5-6 minutes)
  → Main business logic
  → This is where patterns come together

Priority 5 - Quick Usage Example (1 minute)
  → 3-4 lines showing the API in action
```

### What to SKIP (Low Impact):

```
❌ Getters and setters (say "standard getters/setters omitted")
❌ toString(), hashCode(), equals() (mention if relevant)
❌ Exception class definitions (just throw new XException)
❌ Import statements
❌ Main method / driver code (unless asked)
❌ Logging statements
❌ Input validation (mention "would validate here")
❌ Configuration / properties
❌ Database layer / persistence
```

### What to MENTION but Not Implement:

```
→ "I would add input validation here"
→ "This would have proper error handling in production"
→ "I'd use dependency injection for the service"
→ "Logging and metrics would go here"
→ "This map would be a database table in reality"
```

### Code Style During Interview:

```java
// DO: Clean, readable, properly named
class BookingService {
    private final SeatRepository seatRepo;
    private final PaymentProcessor paymentProcessor;
    private final NotificationService notifier;

    public Booking createBooking(User user, Show show, List<Seat> seats) {
        // Lock seats (mention concurrency)
        // Process payment
        // Create booking
        // Notify user
    }
}

// DON'T: Over-engineered or too terse
class Svc {
    public Object doStuff(Object... args) { ... }
}
```

---

## 5. Common Evaluation Criteria

### What Interviewers Look For:

| Criteria | Weight | What They Observe |
|----------|--------|-------------------|
| **Requirement Gathering** | 10% | Did you ask questions before coding? |
| **Object Identification** | 15% | Are entities well-chosen and named? |
| **Relationships** | 10% | Correct use of inheritance/composition |
| **Design Patterns** | 20% | Appropriate pattern selection |
| **SOLID Principles** | 15% | Clean, maintainable design |
| **Code Quality** | 15% | Readable, well-structured code |
| **Extensibility** | 10% | Can the design accommodate changes? |
| **Communication** | 5% | Clear explanation of decisions |

### Red Flags to Avoid:

```
🚫 Starting to code immediately without asking questions
🚫 God class / Manager class that does everything
🚫 Using inheritance where composition fits better
🚫 Hardcoding values instead of using enums/constants
🚫 No interfaces or abstractions (everything concrete)
🚫 Ignoring concurrency in multi-user systems
🚫 Not handling edge cases (full, empty, null)
🚫 Over-engineering (10 patterns for a simple problem)
🚫 Tight coupling between unrelated classes
🚫 Public fields instead of encapsulation
🚫 Circular dependencies between classes
🚫 Using String where enum is appropriate
🚫 Static methods everywhere (hard to test/extend)
🚫 Not following naming conventions
🚫 Mixing business logic with data models
```

### Green Flags to Demonstrate:

```
✅ Ask clarifying questions before designing
✅ Start with high-level design, then drill down
✅ Use proper encapsulation (private fields, public API)
✅ Apply Strategy pattern for varying algorithms
✅ Use composition over inheritance where appropriate
✅ Program to interfaces, not implementations
✅ Single Responsibility - each class has one job
✅ Meaningful naming (BookingService not Manager1)
✅ Consider thread-safety for shared resources
✅ Discuss trade-offs of your design decisions
✅ Show extensibility ("if we need to add X, we just...")
✅ Handle edge cases gracefully
✅ Use enums for fixed categories
✅ Separate data models from business logic (service layer)
✅ Show awareness of SOLID principles naturally
```

### Scoring Rubric (Typical):

```
Strong Hire:
- Clean, extensible design
- 2-3 patterns applied correctly
- SOLID principles evident
- Discussed trade-offs
- Code compiles mentally

Hire:
- Reasonable design
- 1-2 patterns used
- Most SOLID principles followed
- Some extensibility

Lean No Hire:
- Design works but rigid
- No clear patterns
- God class tendencies
- No discussion of trade-offs

No Hire:
- Can't identify objects
- No abstraction
- Spaghetti relationships
- Can't explain decisions
```

---

## 6. Top 20 Must-Prepare Problems (Ranked by Frequency)

### Tier 1: Almost Guaranteed (Prepare These First)

| # | Problem | Key Patterns | Core Classes |
|---|---------|-------------|--------------|
| 1 | **Parking Lot** | Strategy, Factory, Observer | ParkingLot, Floor, Spot, Vehicle, Ticket |
| 2 | **Chess / Tic-Tac-Toe** | Strategy, State, Command | Board, Piece, Player, Move, Game |
| 3 | **BookMyShow (Movie Booking)** | Observer, Strategy, Singleton | Show, Theater, Seat, Booking, Payment |
| 4 | **Elevator System** | Strategy, State, Observer | Elevator, Floor, Request, Dispatcher |
| 5 | **LRU Cache** | - | DoublyLinkedList, HashMap, Node |

### Tier 2: Very Common

| # | Problem | Key Patterns | Core Classes |
|---|---------|-------------|--------------|
| 6 | **Splitwise (Expense Sharing)** | Strategy, Observer | User, Group, Expense, Split, Balance |
| 7 | **Snake and Ladder** | State, Factory | Board, Player, Dice, Cell, Snake, Ladder |
| 8 | **ATM Machine** | State, Chain of Responsibility | ATM, Account, Transaction, CashDispenser |
| 9 | **Vending Machine** | State | VendingMachine, Product, Coin, Inventory |
| 10 | **Library Management** | Observer, Strategy | Library, Book, Member, Loan, Catalog |

### Tier 3: Common

| # | Problem | Key Patterns | Core Classes |
|---|---------|-------------|--------------|
| 11 | **Hotel Booking** | Strategy, Observer | Hotel, Room, Reservation, Guest, Payment |
| 12 | **Food Delivery (Swiggy/Zomato)** | Strategy, Observer, State | Restaurant, Order, DeliveryAgent, Menu |
| 13 | **Cab Booking (Uber/Ola)** | Strategy, Observer, State | Ride, Driver, Rider, Trip, Pricing |
| 14 | **Amazon Shopping** | Strategy, Observer, Factory | Product, Cart, Order, Payment, Catalog |
| 15 | **Stack Overflow** | Observer, Strategy | Question, Answer, User, Vote, Tag |

### Tier 4: Occasionally Asked

| # | Problem | Key Patterns | Core Classes |
|---|---------|-------------|--------------|
| 16 | **LinkedIn** | Observer, Strategy | User, Connection, Post, Message, Job |
| 17 | **Cricinfo (Scorecard)** | Observer, State | Match, Team, Player, Innings, Over, Ball |
| 18 | **Card Game (Blackjack)** | Strategy, State | Deck, Card, Hand, Player, Dealer, Game |
| 19 | **File System** | Composite, Iterator | File, Directory, FileSystem, Permission |
| 20 | **Rate Limiter** | Strategy | RateLimiter, TokenBucket, SlidingWindow |

### Quick Problem-Pattern Mapping:

```
Strategy Pattern     → Parking (spot allocation), Pricing, Sorting
State Pattern        → Vending Machine, ATM, Order Status, Elevator
Observer Pattern     → Notifications, Event systems, Score updates
Factory Pattern      → Vehicle creation, Payment methods, Piece creation
Command Pattern      → Game moves (undo), Transactions
Singleton Pattern    → Cache, Connection Pool, Config Manager
Composite Pattern    → File System, Organization hierarchy
Chain of Resp.       → ATM dispensing, Approval workflows
Builder Pattern      → Complex objects (Pizza, Query, Report)
Decorator Pattern    → Toppings, Feature toggles, Streams
Template Method      → Game loop, Document processing
Iterator Pattern     → Custom collections, Board traversal
```

---

## 7. Quick Reference Card (Interview Day)

### 35-Minute Time Allocation:
```
[0:00 - 2:00]  → Clarify requirements (ASK QUESTIONS)
[2:00 - 5:00]  → Identify objects, draw rough diagram
[5:00 - 7:00]  → Establish relationships
[7:00 - 12:00] → Define interfaces, choose patterns
[12:00 - 27:00]→ Write code (enums → interfaces → models → service)
[27:00 - 30:00]→ Usage example + discuss extensibility
[30:00 - 35:00]→ Handle interviewer questions
```

### SOLID Principles Cheat Sheet:
```
S - Single Responsibility  → One class, one reason to change
O - Open/Closed           → Extend behavior without modifying existing code
L - Liskov Substitution   → Subtypes must be usable as their base type
I - Interface Segregation → Many specific interfaces > one fat interface
D - Dependency Inversion  → Depend on abstractions, not concretions
```

### Key Phrases to Use:
```
"Let me start by clarifying the requirements..."
"I'll identify the core entities first..."
"This follows the Strategy pattern because..."
"I'm using composition here because the lifecycle..."
"This is extensible - if we need to add X, we just implement..."
"The trade-off here is X vs Y, I chose X because..."
"I would add thread-safety here using..."
"Let me walk through a use case to verify..."
```

### Anti-Patterns to Call Out:
```
"I'm avoiding a God class by separating..."
"Instead of if-else chains, I'm using Strategy..."
"Rather than inheritance, I'm using composition because..."
"I'm programming to the interface so we can swap..."
```

---

## 8. Practice Checklist

### Before the Interview:
- [ ] Practice 5 problems end-to-end (timed 35 min each)
- [ ] Know 5 design patterns cold (Strategy, Observer, Factory, State, Singleton)
- [ ] Be able to draw UML class diagrams quickly
- [ ] Practice explaining decisions out loud
- [ ] Have your "framework" memorized (the 7 steps above)

### During the Interview:
- [ ] Asked at least 3 clarifying questions
- [ ] Identified core entities before coding
- [ ] Stated relationships explicitly
- [ ] Used at least 1 interface
- [ ] Applied at least 1 design pattern
- [ ] Wrote compilable-looking code
- [ ] Discussed extensibility
- [ ] Mentioned thread-safety (if applicable)

### Common Mistakes in Practice:
```
Mistake 1: Spending too long on perfect UML
  Fix: Rough sketch is fine, move to code quickly

Mistake 2: Implementing everything
  Fix: Focus on core 2-3 classes + service layer

Mistake 3: Not talking while coding
  Fix: Narrate your decisions ("I'm using X because...")

Mistake 4: Getting stuck on syntax
  Fix: Pseudocode is acceptable, logic matters more

Mistake 5: Forgetting the service/manager layer
  Fix: Always have a class that orchestrates the flow
```

---

## Summary

The LLD interview is about demonstrating **structured thinking**, not perfection. Follow the framework:

1. **Ask** → Don't assume
2. **Identify** → Nouns become classes
3. **Relate** → IS-A, HAS-A, USES-A
4. **Abstract** → Interfaces for flexibility
5. **Pattern** → Apply 1-2 patterns correctly
6. **Code** → Enums first, service last
7. **Discuss** → Extensibility and trade-offs

Master these 7 steps, and you'll handle any LLD interview confidently.
