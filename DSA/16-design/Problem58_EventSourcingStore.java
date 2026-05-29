import java.util.*;
import java.util.concurrent.*;
import java.util.function.*;

/**
 * Problem 58: Event Sourcing Store (Append Log, Snapshots, Replay)
 * 
 * PRODUCTION MAPPING: EventStoreDB, Axon Framework, Kafka (as event log),
 *                     Banking/Financial systems, CQRS architectures
 * 
 * Core Concepts:
 * - State is derived from a sequence of events, never stored directly
 * - Append-only log: immutable, auditable, replayable
 * - Snapshots: periodic state checkpoints to avoid replaying entire history
 * - Projections: derive read models by replaying events
 * 
 * Design Decisions:
 * - Events are immutable value objects with metadata (timestamp, version, type)
 * - Aggregate pattern: events grouped by aggregate ID
 * - Optimistic concurrency: expected version on write to prevent conflicts
 * - Snapshot every N events to bound replay time
 * 
 * Trade-offs:
 * - Append-only = unlimited audit trail but growing storage
 * - Snapshots reduce replay time but add complexity
 * - Event schema evolution is hard (need upcasters)
 */
public class Problem58_EventSourcingStore {

    // ---- Events ----
    static class Event {
        final String aggregateId;
        final String type;
        final Map<String, Object> data;
        final long timestamp;
        final int version; // sequence number within aggregate

        Event(String aggregateId, String type, Map<String, Object> data, int version) {
            this.aggregateId = aggregateId;
            this.type = type;
            this.data = Collections.unmodifiableMap(data);
            this.timestamp = System.currentTimeMillis();
            this.version = version;
        }

        @Override
        public String toString() {
            return String.format("Event{%s v%d %s %s}", aggregateId, version, type, data);
        }
    }

    static class Snapshot<T> {
        final String aggregateId;
        final T state;
        final int version; // version at which snapshot was taken

        Snapshot(String aggregateId, T state, int version) {
            this.aggregateId = aggregateId;
            this.state = state;
            this.version = version;
        }
    }

    // ---- Event Store ----
    static class EventStore {
        private final Map<String, List<Event>> streams = new ConcurrentHashMap<>();
        private final Map<String, Snapshot<?>> snapshots = new ConcurrentHashMap<>();
        private final List<Event> globalLog = new CopyOnWriteArrayList<>(); // for projections
        private final int snapshotInterval;

        // Subscribers for real-time projections
        private final List<Consumer<Event>> subscribers = new CopyOnWriteArrayList<>();

        public EventStore(int snapshotInterval) {
            this.snapshotInterval = snapshotInterval;
        }

        /**
         * Append events with optimistic concurrency control.
         * expectedVersion = last known version. If mismatch, concurrent modification detected.
         */
        public synchronized void append(String aggregateId, List<Event> events, int expectedVersion) {
            List<Event> stream = streams.computeIfAbsent(aggregateId, k -> new ArrayList<>());
            
            int currentVersion = stream.isEmpty() ? 0 : stream.get(stream.size() - 1).version;
            if (currentVersion != expectedVersion) {
                throw new ConcurrentModificationException(
                    "Expected version " + expectedVersion + " but got " + currentVersion);
            }

            stream.addAll(events);
            globalLog.addAll(events);

            // Notify subscribers (for real-time projections)
            for (Event e : events) {
                for (Consumer<Event> sub : subscribers) {
                    sub.accept(e);
                }
            }
        }

        public List<Event> getEvents(String aggregateId) {
            return streams.getOrDefault(aggregateId, Collections.emptyList());
        }

        public List<Event> getEventsSince(String aggregateId, int sinceVersion) {
            List<Event> all = getEvents(aggregateId);
            List<Event> result = new ArrayList<>();
            for (Event e : all) {
                if (e.version > sinceVersion) result.add(e);
            }
            return result;
        }

        public <T> void saveSnapshot(String aggregateId, T state, int version) {
            snapshots.put(aggregateId, new Snapshot<>(aggregateId, state, version));
        }

        @SuppressWarnings("unchecked")
        public <T> Snapshot<T> getSnapshot(String aggregateId) {
            return (Snapshot<T>) snapshots.get(aggregateId);
        }

        public void subscribe(Consumer<Event> listener) {
            subscribers.add(listener);
        }

        public List<Event> getGlobalLog() { return globalLog; }
        public int getSnapshotInterval() { return snapshotInterval; }
    }

    // ---- Example Aggregate: Bank Account ----
    static class BankAccount {
        String accountId;
        long balance;
        int version;
        List<String> transactionHistory = new ArrayList<>();

        BankAccount(String accountId) {
            this.accountId = accountId;
            this.balance = 0;
            this.version = 0;
        }

        // Apply event to rebuild state
        void apply(Event event) {
            switch (event.type) {
                case "AccountOpened":
                    this.balance = ((Number) event.data.get("initialBalance")).longValue();
                    break;
                case "MoneyDeposited":
                    this.balance += ((Number) event.data.get("amount")).longValue();
                    break;
                case "MoneyWithdrawn":
                    this.balance -= ((Number) event.data.get("amount")).longValue();
                    break;
            }
            this.version = event.version;
            transactionHistory.add(event.type + ":" + event.data);
        }

        // Rebuild from events (with optional snapshot)
        static BankAccount rebuild(EventStore store, String accountId) {
            BankAccount account = new BankAccount(accountId);

            // Try loading from snapshot first
            Snapshot<BankAccount> snapshot = store.getSnapshot(accountId);
            if (snapshot != null) {
                account.balance = snapshot.state.balance;
                account.version = snapshot.version;
                account.transactionHistory = new ArrayList<>(snapshot.state.transactionHistory);
                // Only replay events after snapshot
                for (Event e : store.getEventsSince(accountId, snapshot.version)) {
                    account.apply(e);
                }
            } else {
                // Full replay
                for (Event e : store.getEvents(accountId)) {
                    account.apply(e);
                }
            }

            // Save snapshot if enough events accumulated
            if (account.version > 0 && account.version % store.getSnapshotInterval() == 0) {
                BankAccount snap = new BankAccount(accountId);
                snap.balance = account.balance;
                snap.version = account.version;
                snap.transactionHistory = new ArrayList<>(account.transactionHistory);
                store.saveSnapshot(accountId, snap, account.version);
            }

            return account;
        }
    }

    // Helper to create events
    static Event event(String aggId, String type, Map<String, Object> data, int version) {
        return new Event(aggId, type, data, version);
    }

    public static void main(String[] args) {
        System.out.println("=== Event Sourcing Store ===\n");

        EventStore store = new EventStore(5); // snapshot every 5 events

        // Test 1: Append and replay events
        String accId = "acc-001";
        store.append(accId, List.of(
            event(accId, "AccountOpened", Map.of("initialBalance", 1000), 1),
            event(accId, "MoneyDeposited", Map.of("amount", 500), 2),
            event(accId, "MoneyWithdrawn", Map.of("amount", 200), 3)
        ), 0);

        BankAccount account = BankAccount.rebuild(store, accId);
        assert account.balance == 1300 : "Expected 1300, got: " + account.balance;
        assert account.version == 3;
        System.out.println("PASS: Event replay produces correct state (balance=1300)");

        // Test 2: Optimistic concurrency control
        try {
            store.append(accId, List.of(
                event(accId, "MoneyDeposited", Map.of("amount", 100), 4)
            ), 2); // wrong expected version (should be 3)
            assert false : "Should throw";
        } catch (ConcurrentModificationException e) {
            System.out.println("PASS: Optimistic concurrency rejects stale write");
        }

        // Test 3: Successful append with correct version
        store.append(accId, List.of(
            event(accId, "MoneyDeposited", Map.of("amount", 100), 4),
            event(accId, "MoneyDeposited", Map.of("amount", 100), 5)
        ), 3);
        account = BankAccount.rebuild(store, accId);
        assert account.balance == 1500;
        assert account.version == 5;
        System.out.println("PASS: Append with correct version succeeds (balance=1500)");

        // Test 4: Snapshot created at version 5
        Snapshot<BankAccount> snap = store.getSnapshot(accId);
        assert snap != null : "Snapshot should exist at version 5";
        assert snap.version == 5;
        System.out.println("PASS: Snapshot created at interval (version=5)");

        // Test 5: Rebuild from snapshot + partial replay
        store.append(accId, List.of(
            event(accId, "MoneyWithdrawn", Map.of("amount", 50), 6)
        ), 5);
        account = BankAccount.rebuild(store, accId);
        assert account.balance == 1450 : "Expected 1450, got: " + account.balance;
        System.out.println("PASS: Rebuild from snapshot + replay (balance=1450)");

        // Test 6: Full audit trail preserved
        List<Event> fullHistory = store.getEvents(accId);
        assert fullHistory.size() == 6 : "All 6 events preserved";
        System.out.println("PASS: Full audit trail: " + fullHistory.size() + " events");

        // Test 7: Real-time projection via subscriber
        List<String> projectedDeposits = new CopyOnWriteArrayList<>();
        store.subscribe(e -> {
            if (e.type.equals("MoneyDeposited")) {
                projectedDeposits.add(e.aggregateId + ":" + e.data.get("amount"));
            }
        });
        store.append("acc-002", List.of(
            event("acc-002", "AccountOpened", Map.of("initialBalance", 0), 1),
            event("acc-002", "MoneyDeposited", Map.of("amount", 999), 2)
        ), 0);
        assert projectedDeposits.size() == 1;
        System.out.println("PASS: Real-time projection received deposit event");

        // Test 8: Multiple aggregates isolated
        BankAccount acc2 = BankAccount.rebuild(store, "acc-002");
        assert acc2.balance == 999;
        account = BankAccount.rebuild(store, accId);
        assert account.balance == 1450;
        System.out.println("PASS: Aggregates are isolated");

        System.out.println("\nAll tests passed!");
    }
}
