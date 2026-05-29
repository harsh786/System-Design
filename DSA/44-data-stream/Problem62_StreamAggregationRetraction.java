import java.util.*;

/**
 * Problem 62: Stream Aggregation with Retraction
 * 
 * Production Relevance:
 * - When upstream corrects/updates a record, downstream aggregations must retract old + add new
 * - Changelog semantics: +I (insert), -U (update before), +U (update after), -D (delete)
 * - Used in materialized views, real-time OLAP, Flink dynamic tables
 * - Without retraction: aggregates drift from truth over time
 * 
 * Architect Considerations:
 * - Must maintain per-key state to know what was previously contributed
 * - Retraction doubles message volume (negative + positive for each update)
 * - Some aggregates support retraction natively (sum, count) others don't (min, max)
 */
public class Problem62_StreamAggregationRetraction {

    enum ChangeType { INSERT, UPDATE_BEFORE, UPDATE_AFTER, DELETE }

    static class ChangeEvent {
        ChangeType type;
        String key;
        String groupBy;
        double value;

        ChangeEvent(ChangeType type, String key, String groupBy, double value) {
            this.type = type; this.key = key; this.groupBy = groupBy; this.value = value;
        }
    }

    static class RetractableAggregate {
        double sum = 0;
        long count = 0;

        void add(double value) { sum += value; count++; }
        void retract(double value) { sum -= value; count--; }
        double getAvg() { return count == 0 ? 0 : sum / count; }

        @Override
        public String toString() {
            return String.format("sum=%.1f, count=%d, avg=%.2f", sum, count, getAvg());
        }
    }

    static class RetractingAggregator {
        // group -> aggregate
        private final Map<String, RetractableAggregate> aggregates = new HashMap<>();
        // key -> (group, last contributed value) for retraction
        private final Map<String, Map.Entry<String, Double>> lastValues = new HashMap<>();
        private final List<String> log = new ArrayList<>();

        public void process(ChangeEvent event) {
            switch (event.type) {
                case INSERT: {
                    RetractableAggregate agg = aggregates.computeIfAbsent(event.groupBy, k -> new RetractableAggregate());
                    agg.add(event.value);
                    lastValues.put(event.key, Map.entry(event.groupBy, event.value));
                    log.add(String.format("+I [%s] group=%s val=%.1f -> %s", event.key, event.groupBy, event.value, agg));
                    break;
                }
                case UPDATE_BEFORE: {
                    // Retract old value
                    Map.Entry<String, Double> prev = lastValues.get(event.key);
                    if (prev != null) {
                        RetractableAggregate agg = aggregates.get(prev.getKey());
                        if (agg != null) agg.retract(prev.getValue());
                        log.add(String.format("-U [%s] retract val=%.1f from group=%s -> %s", event.key, prev.getValue(), prev.getKey(), agg));
                    }
                    break;
                }
                case UPDATE_AFTER: {
                    RetractableAggregate agg = aggregates.computeIfAbsent(event.groupBy, k -> new RetractableAggregate());
                    agg.add(event.value);
                    lastValues.put(event.key, Map.entry(event.groupBy, event.value));
                    log.add(String.format("+U [%s] group=%s val=%.1f -> %s", event.key, event.groupBy, event.value, agg));
                    break;
                }
                case DELETE: {
                    Map.Entry<String, Double> prev = lastValues.remove(event.key);
                    if (prev != null) {
                        RetractableAggregate agg = aggregates.get(prev.getKey());
                        if (agg != null) agg.retract(prev.getValue());
                        log.add(String.format("-D [%s] retract val=%.1f from group=%s -> %s", event.key, prev.getValue(), prev.getKey(), agg));
                    }
                    break;
                }
            }
        }

        public void printLog() { log.forEach(System.out::println); }
        public Map<String, RetractableAggregate> getAggregates() { return aggregates; }
    }

    public static void main(String[] args) {
        System.out.println("=== Stream Aggregation with Retraction ===\n");
        System.out.println("Scenario: SUM(revenue) GROUP BY region\n");

        RetractingAggregator agg = new RetractingAggregator();

        // Initial inserts
        agg.process(new ChangeEvent(ChangeType.INSERT, "order1", "US", 100));
        agg.process(new ChangeEvent(ChangeType.INSERT, "order2", "US", 200));
        agg.process(new ChangeEvent(ChangeType.INSERT, "order3", "EU", 150));

        // Update: order1 changes from 100 to 120 (retract 100, add 120)
        agg.process(new ChangeEvent(ChangeType.UPDATE_BEFORE, "order1", "US", 100));
        agg.process(new ChangeEvent(ChangeType.UPDATE_AFTER, "order1", "US", 120));

        // Delete: order2 cancelled
        agg.process(new ChangeEvent(ChangeType.DELETE, "order2", "US", 200));

        System.out.println("Processing log:");
        agg.printLog();
        System.out.println("\nFinal aggregates:");
        agg.getAggregates().forEach((k, v) -> System.out.printf("  %s: %s%n", k, v));
    }
}
