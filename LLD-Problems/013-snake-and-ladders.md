# 013. Design Snake And Ladders

Source problem: `Design snake and ladders.`  
Category: `Game`  
Primary focus: `board generation, dice, turns, movement rules`  
Archetype: `game`

## 1. Interview Framing

Design `snake and ladders` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `snake and ladders` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `WAITING_FOR_ROLL, MOVING, EXTRA_TURN, FINISHED, CANCELLED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.
- Separate board state from rules so alternate game variants can be plugged in.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.
- A complete graphics engine or multiplayer networking stack.

## 4. Actors And Use Cases

Actors:

- `Player`
- `GameHost`
- `RandomProvider`

Primary use cases:

- `rollDice` command on `SnakeAndLadders`
- `moveToken` command on `SnakeAndLadders`
- `applyJump` command on `SnakeAndLadders`
- `declareWinner` command on `SnakeAndLadders`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `SnakeAndLadders` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Board, Cell, Snake, Ladder, Dice` | Have identity and change over time under the aggregate. |
| Value objects | `Position, DiceRoll, PlayerToken` | Immutable concepts compared by value. |
| Policies | `SnakeAndLaddersPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `SnakeAndLaddersRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
WAITING_FOR_ROLL, MOVING, EXTRA_TURN, FINISHED, CANCELLED
```

Invariants:

- `SnakeAndLadders` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.
- A move is applied only if it is legal for the current turn, board, and rule set.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `SnakeAndLaddersService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `SnakeAndLadders` | Composes | Board, Cell, Snake | Owns invariants and lifecycle transitions. |
| `SnakeAndLaddersRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `SnakeAndLaddersPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class SnakeAndLadders {
  +UUID id
  +SnakeAndLaddersStatus status
  +long version
  +validateInvariants()
}
class SnakeAndLaddersService {
  +handle(command)
}
class SnakeAndLaddersRepository {
  <<interface>>
  +findById(UUID id) SnakeAndLadders
  +save(SnakeAndLadders aggregate, long expectedVersion)
}
class SnakeAndLaddersPolicy {
  <<interface>>
  +evaluate(context) Decision
}
SnakeAndLaddersService --> SnakeAndLaddersRepository
SnakeAndLaddersService --> SnakeAndLaddersPolicy
SnakeAndLaddersService --> SnakeAndLadders
class Board {
  +UUID id
  +validate()
}
SnakeAndLadders "1" o-- "many" Board
class Cell {
  +UUID id
  +validate()
}
SnakeAndLadders "1" o-- "many" Cell
class Snake {
  +UUID id
  +validate()
}
SnakeAndLadders "1" o-- "many" Snake
class Ladder {
  +UUID id
  +validate()
}
SnakeAndLadders "1" o-- "many" Ladder
class Position {
  <<value object>>
}
SnakeAndLadders ..> Position
class DiceRoll {
  <<value object>>
}
SnakeAndLadders ..> DiceRoll
class PlayerToken {
  <<value object>>
}
SnakeAndLadders ..> PlayerToken
SnakeAndLaddersPolicy <|.. MoveValidationStrategy
SnakeAndLadders ..> RulesEngine
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as SnakeAndLaddersService
participant Repo as SnakeAndLaddersRepository
participant Policy as SnakeAndLaddersPolicy
participant Agg as SnakeAndLadders
participant Outbox
Client->>Service: rollDice(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: rollDice(command)
Agg-->>Service: SnakeAndLaddersRollDiceEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| Specification | Compose business predicates and keep rule evaluation explainable. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.snakeandladders;

import java.util.*;

record Position(int row, int column) {}
record Move(UUID playerId, Position from, Position to, Map<String, String> metadata) {}
record MoveResult(boolean accepted, String reason) {
    static MoveResult accepted() { return new MoveResult(true, "accepted"); }
    static MoveResult rejected(String reason) { return new MoveResult(false, reason); }
}

enum SnakeAndLaddersStatus {
    WAITING_FOR_ROLL,
    MOVING,
    EXTRA_TURN,
    FINISHED,
    CANCELLED
}

interface MoveRule {
    MoveResult validate(SnakeAndLadders game, Move move);
}

final class Board {
    private final int rows;
    private final int columns;
    private final Map<Position, String> pieces = new HashMap<>();

    Board(int rows, int columns) {
        this.rows = rows;
        this.columns = columns;
    }

    boolean inside(Position p) {
        return p.row() >= 0 && p.row() < rows && p.column() >= 0 && p.column() < columns;
    }

    Optional<String> pieceAt(Position p) {
        return Optional.ofNullable(pieces.get(p));
    }

    void move(Position from, Position to) {
        String piece = pieces.remove(from);
        if (piece == null) throw new IllegalStateException("No piece at " + from);
        pieces.put(to, piece);
    }
}

final class SnakeAndLadders {
    private final UUID id = UUID.randomUUID();
    private final Board board;
    private final List<MoveRule> rules;
    private SnakeAndLaddersStatus status = SnakeAndLaddersStatus.WAITING_FOR_ROLL;
    private UUID currentPlayerId;

    SnakeAndLadders(Board board, List<MoveRule> rules, UUID firstPlayerId) {
        this.board = Objects.requireNonNull(board);
        this.rules = List.copyOf(rules);
        this.currentPlayerId = Objects.requireNonNull(firstPlayerId);
    }

    public MoveResult applyMove(Move move) {
        if (!move.playerId().equals(currentPlayerId)) return MoveResult.rejected("not current player's turn");
        for (MoveRule rule : rules) {
            MoveResult result = rule.validate(this, move);
            if (!result.accepted()) return result;
        }
        board.move(move.from(), move.to());
        status = SnakeAndLaddersStatus.MOVING;
        return MoveResult.accepted();
    }

    public Board board() { return board; }
    public SnakeAndLaddersStatus status() { return status; }
    public UUID id() { return id; }
}
```

## 11. Concurrency And Thread Safety

- Use optimistic concurrency on aggregate save: `save(aggregate, expectedVersion)`.
- Lock scarce resources such as seats, rooms, inventory, accounts, or tasks with short-lived holds.
- Make commands idempotent when callers can retry after timeout.
- Publish events through an outbox in the same transaction as the aggregate update.

## 12. Persistence And Transactions

- Persist `SnakeAndLadders` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
- Persist child entities in owned tables/documents keyed by aggregate id.
- Store domain events in an outbox table in the same transaction.
- Add indexes for business lookup keys, active state, owner/user id, and expiry deadlines.

## 13. Error Handling And Idempotency

- Return typed domain errors: `NotFound`, `InvalidState`, `PolicyRejected`, `Conflict`, and `DuplicateCommand`.
- Never partially mutate aggregate state before all guards pass.
- Log rejection reasons with correlation id; avoid logging secrets, tokens, or sensitive payloads.

## 14. Extensibility Hooks

| Change point | Extension mechanism |
|---|---|
| Compose business predicates and keep rule evaluation explainable. | `Specification` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `SnakeAndLadders` invariants and each command method.
- State-machine test all valid and invalid `SnakeAndLaddersStatus` transitions.
- Contract test every `SnakeAndLaddersRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.
- Property tests for legal move generation and terminal result detection.

## 16. Interview Tips

1. Start with the invariant: `SnakeAndLadders` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `SnakeAndLaddersService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
