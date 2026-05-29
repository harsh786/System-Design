import java.util.*;

/**
 * Problem 63: Changelog Stream (CDC) Processing
 * 
 * Production Relevance:
 * - Change Data Capture: stream database changes (Debezium, DynamoDB Streams, Postgres WAL)
 * - Enables real-time data sync, materialized views, event sourcing from existing DBs
 * - Core pattern for database-to-stream bridge without dual writes
 * - Used in data lake ingestion, cache invalidation, search index updates
 * 
 * Architect Considerations:
 * - Must handle schema evolution in CDC events
 * - Ordering guarantees: per-key ordering from WAL, cross-key ordering not guaranteed
 * - Snapshot + incremental: bootstrap full state then apply changes
 * - Tombstones (null values) for deletes in compacted topics
 */
public class Problem63_ChangelogStreamCDCProcessing {

    enum Operation { CREATE, UPDATE, DELETE, READ } // READ = snapshot

    static class CDCEvent {
        Operation op;
        String table;
        Map<String, Object> before; // null for CREATE
        Map<String, Object> after;  // null for DELETE
        long lsn; // log sequence number
        long timestamp;

        CDCEvent(Operation op, String table, Map<String, Object> before, Map<String, Object> after, long lsn) {
            this.op = op; this.table = table; this.before = before;
            this.after = after; this.lsn = lsn; this.timestamp = System.currentTimeMillis();
        }

        String getKey() {
            Map<String, Object> record = after != null ? after : before;
            return record != null ? String.valueOf(record.get("id")) : "unknown";
        }
    }

    // Materializes a table from CDC stream
    static class MaterializedTable {
        private final Map<String, Map<String, Object>> state = new LinkedHashMap<>();
        private long lastProcessedLsn = -1;
        private final List<String> appliedOps = new ArrayList<>();

        public void apply(CDCEvent event) {
            if (event.lsn <= lastProcessedLsn) return; // Idempotent
            lastProcessedLsn = event.lsn;

            String key = event.getKey();
            switch (event.op) {
                case CREATE:
                case READ: // Snapshot records treated as creates
                    state.put(key, new HashMap<>(event.after));
                    appliedOps.add(String.format("INSERT %s: %s", key, event.after));
                    break;
                case UPDATE:
                    if (state.containsKey(key)) {
                        state.put(key, new HashMap<>(event.after));
                        appliedOps.add(String.format("UPDATE %s: %s -> %s", key, event.before, event.after));
                    }
                    break;
                case DELETE:
                    state.remove(key);
                    appliedOps.add(String.format("DELETE %s: was %s", key, event.before));
                    break;
            }
        }

        public Map<String, Object> get(String key) { return state.get(key); }
        public int size() { return state.size(); }
        public void printState() {
            state.forEach((k, v) -> System.out.printf("  %s: %s%n", k, v));
        }
        public List<String> getAppliedOps() { return appliedOps; }
    }

    public static void main(String[] args) {
        System.out.println("=== Changelog Stream (CDC) Processing ===\n");

        MaterializedTable users = new MaterializedTable();

        // Simulate Debezium CDC events from 'users' table
        List<CDCEvent> cdcStream = List.of(
            // Snapshot phase
            new CDCEvent(Operation.READ, "users", null, Map.of("id", "1", "name", "Alice", "email", "alice@ex.com"), 1),
            new CDCEvent(Operation.READ, "users", null, Map.of("id", "2", "name", "Bob", "email", "bob@ex.com"), 2),
            // Incremental phase
            new CDCEvent(Operation.CREATE, "users", null, Map.of("id", "3", "name", "Charlie", "email", "charlie@ex.com"), 3),
            new CDCEvent(Operation.UPDATE, "users",
                Map.of("id", "1", "name", "Alice", "email", "alice@ex.com"),
                Map.of("id", "1", "name", "Alice", "email", "alice@new.com"), 4),
            new CDCEvent(Operation.DELETE, "users", Map.of("id", "2", "name", "Bob", "email", "bob@ex.com"), null, 5),
            // Duplicate (idempotency test)
            new CDCEvent(Operation.DELETE, "users", Map.of("id", "2", "name", "Bob", "email", "bob@ex.com"), null, 5)
        );

        for (CDCEvent event : cdcStream) {
            users.apply(event);
        }

        System.out.println("Applied operations:");
        users.getAppliedOps().forEach(op -> System.out.println("  " + op));
        System.out.println("\nMaterialized table state (" + users.size() + " rows):");
        users.printState();
    }
}
