import java.util.*;
import java.util.concurrent.*;

/**
 * Problem 52: Windowed Join (Stream-Table)
 * 
 * Production Relevance:
 * - Enrichment pattern: join streaming events with a materialized table (e.g., user profile lookup)
 * - Table side is a compacted changelog (latest value per key) - no window needed on table side
 * - Used in Kafka Streams KStream-KTable join, Flink temporal joins
 * - Critical for real-time feature enrichment in ML pipelines
 * 
 * Architect Considerations:
 * - Table must be fully materialized before stream processing begins (bootstrap)
 * - Table updates propagate to future stream joins immediately
 * - Unlike stream-stream join, this is asymmetric: stream drives output, table provides context
 */
public class Problem52_WindowedJoinStreamTable {

    static class StreamEvent {
        String key;
        String payload;
        long timestamp;

        StreamEvent(String key, String payload, long timestamp) {
            this.key = key;
            this.payload = payload;
            this.timestamp = timestamp;
        }
    }

    static class TableRecord {
        String key;
        String value;
        long updatedAt;

        TableRecord(String key, String value, long updatedAt) {
            this.key = key;
            this.value = value;
            this.updatedAt = updatedAt;
        }
    }

    static class EnrichedEvent {
        StreamEvent event;
        TableRecord enrichment;

        EnrichedEvent(StreamEvent event, TableRecord enrichment) {
            this.event = event;
            this.enrichment = enrichment;
        }

        @Override
        public String toString() {
            String enrichVal = enrichment != null ? enrichment.value : "NULL";
            return String.format("Enriched{key=%s, payload=%s, enrichedWith=%s}",
                    event.key, event.payload, enrichVal);
        }
    }

    static class StreamTableJoin {
        // Materialized table state (compacted - only latest per key)
        private final Map<String, TableRecord> tableState = new ConcurrentHashMap<>();
        private final List<EnrichedEvent> output = new ArrayList<>();

        // Table side: upsert
        public void updateTable(TableRecord record) {
            if (record.value == null) {
                tableState.remove(record.key); // Tombstone = delete
            } else {
                tableState.put(record.key, record);
            }
        }

        // Stream side: lookup and join
        public EnrichedEvent processStreamEvent(StreamEvent event) {
            TableRecord tableRecord = tableState.get(event.key);
            EnrichedEvent enriched = new EnrichedEvent(event, tableRecord);
            output.add(enriched);
            return enriched;
        }

        // Left join: emit even if table has no match
        public EnrichedEvent processStreamEventLeftJoin(StreamEvent event) {
            return processStreamEvent(event); // Same logic, null enrichment is acceptable
        }

        // Inner join: only emit if table has match
        public EnrichedEvent processStreamEventInnerJoin(StreamEvent event) {
            TableRecord tableRecord = tableState.get(event.key);
            if (tableRecord == null) return null;
            EnrichedEvent enriched = new EnrichedEvent(event, tableRecord);
            output.add(enriched);
            return enriched;
        }

        public int getTableSize() {
            return tableState.size();
        }
    }

    public static void main(String[] args) {
        StreamTableJoin join = new StreamTableJoin();

        System.out.println("=== Stream-Table Join (Enrichment Pattern) ===\n");

        // Bootstrap table with user profiles
        join.updateTable(new TableRecord("user1", "profile:{name:Alice,tier:gold}", 0));
        join.updateTable(new TableRecord("user2", "profile:{name:Bob,tier:silver}", 0));
        System.out.println("Table bootstrapped with " + join.getTableSize() + " records");

        // Stream events arrive and get enriched
        EnrichedEvent e1 = join.processStreamEvent(new StreamEvent("user1", "page_view:/dashboard", 1000));
        System.out.println(e1);

        EnrichedEvent e2 = join.processStreamEvent(new StreamEvent("user3", "page_view:/home", 2000));
        System.out.println(e2 + " (no table match - left join returns null enrichment)");

        // Table update: user2 upgrades tier
        join.updateTable(new TableRecord("user2", "profile:{name:Bob,tier:gold}", 3000));

        // New stream event for user2 sees updated table
        EnrichedEvent e3 = join.processStreamEvent(new StreamEvent("user2", "purchase:item123", 4000));
        System.out.println(e3 + " (sees updated tier)");

        // Inner join: user3 filtered out
        EnrichedEvent e4 = join.processStreamEventInnerJoin(new StreamEvent("user3", "click:button", 5000));
        System.out.println("Inner join for unknown user: " + e4);
    }
}
