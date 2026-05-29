import java.util.*;

/**
 * Problem 58: Real-time Event Prioritizer
 * 
 * Production Relevance:
 * - Event-driven systems must prioritize processing of high-value events
 * - Security alerts > system errors > business events > analytics
 * - Used in SIEM systems (Splunk, Sentinel), notification systems, IoT event hubs
 * - Must handle burst of events without dropping critical ones
 * 
 * Architect Considerations:
 * - Multi-dimensional priority: severity * urgency * business_value
 * - Bounded priority queue with eviction of lowest priority on overflow
 * - Real-time: O(log n) insert and extract-max
 */
public class Problem58_RealTimeEventPrioritizer {

    enum Severity { CRITICAL, HIGH, MEDIUM, LOW, INFO }

    static class Event {
        String id;
        String source;
        Severity severity;
        double businessValue; // 0-100
        long timestamp;
        boolean timeDecaying; // priority decreases over time

        Event(String id, String source, Severity sev, double bizValue, boolean decaying) {
            this.id = id; this.source = source; this.severity = sev;
            this.businessValue = bizValue; this.timestamp = System.nanoTime();
            this.timeDecaying = decaying;
        }

        double computePriority(long currentTime) {
            double base = (5 - severity.ordinal()) * 20 + businessValue;
            if (timeDecaying) {
                double ageSeconds = (currentTime - timestamp) / 1_000_000_000.0;
                base *= Math.exp(-0.1 * ageSeconds); // exponential decay
            }
            return base;
        }
    }

    static class BoundedPriorityEventQueue {
        private final int capacity;
        private final PriorityQueue<Event> minHeap; // min-heap for eviction of lowest
        private final long startTime = System.nanoTime();
        private int evictedCount = 0;

        BoundedPriorityEventQueue(int capacity) {
            this.capacity = capacity;
            this.minHeap = new PriorityQueue<>(Comparator.comparingDouble(e -> e.computePriority(System.nanoTime())));
        }

        boolean offer(Event event) {
            if (minHeap.size() < capacity) {
                minHeap.offer(event);
                return true;
            }
            // Check if new event has higher priority than lowest in queue
            Event lowest = minHeap.peek();
            long now = System.nanoTime();
            if (event.computePriority(now) > lowest.computePriority(now)) {
                minHeap.poll(); // evict lowest
                minHeap.offer(event);
                evictedCount++;
                return true;
            }
            evictedCount++;
            return false; // new event is too low priority
        }

        // Get highest priority event (rebuild as max-heap query)
        Event pollHighest() {
            if (minHeap.isEmpty()) return null;
            long now = System.nanoTime();
            List<Event> all = new ArrayList<>(minHeap);
            all.sort((a, b) -> Double.compare(b.computePriority(now), a.computePriority(now)));
            Event highest = all.get(0);
            minHeap.remove(highest);
            return highest;
        }

        int size() { return minHeap.size(); }
        int getEvictedCount() { return evictedCount; }
    }

    public static void main(String[] args) {
        System.out.println("=== Real-time Event Prioritizer ===\n");

        BoundedPriorityEventQueue queue = new BoundedPriorityEventQueue(5);

        Event[] events = {
            new Event("evt1", "monitor", Severity.INFO, 10, false),
            new Event("evt2", "security", Severity.CRITICAL, 95, false),
            new Event("evt3", "app", Severity.HIGH, 60, true),
            new Event("evt4", "db", Severity.MEDIUM, 40, false),
            new Event("evt5", "network", Severity.LOW, 20, true),
            new Event("evt6", "security", Severity.CRITICAL, 99, false), // should evict lowest
            new Event("evt7", "app", Severity.HIGH, 70, false),          // should evict next lowest
        };

        System.out.println("Inserting events (capacity=5):");
        for (Event e : events) {
            boolean accepted = queue.offer(e);
            System.out.printf("  %-6s %-9s biz=%.0f -> %s%n",
                    e.id, e.severity, e.businessValue, accepted ? "ACCEPTED" : "REJECTED");
        }

        System.out.printf("\nQueue size: %d, Evicted: %d%n", queue.size(), queue.getEvictedCount());
        System.out.println("\nProcessing order (highest priority first):");
        Event e;
        while ((e = queue.pollHighest()) != null) {
            System.out.printf("  %s [%s] from %s, priority=%.1f%n",
                    e.id, e.severity, e.source, e.computePriority(System.nanoTime()));
        }
    }
}
