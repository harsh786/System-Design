import java.util.*;
import java.util.concurrent.*;

/**
 * Problem 51: Windowed Join (Stream-Stream)
 * 
 * Production Relevance:
 * - Core pattern in event-driven architectures (e.g., joining clickstream with purchase events)
 * - Used in Kafka Streams, Flink, Spark Structured Streaming
 * - Window-based joins handle the infinite nature of streams by bounding join scope
 * - Critical for correlating events from different microservices within a time window
 * 
 * Architect Considerations:
 * - Window size determines memory usage and join completeness tradeoff
 * - Late arrivals may miss the join window - need watermark strategy
 * - State store cleanup is essential to prevent OOM in long-running jobs
 */
public class Problem51_WindowedJoinStreamStream {

    static class Event {
        String key;
        String value;
        long timestamp;

        Event(String key, String value, long timestamp) {
            this.key = key;
            this.value = value;
            this.timestamp = timestamp;
        }

        @Override
        public String toString() {
            return String.format("Event{key='%s', value='%s', ts=%d}", key, value, timestamp);
        }
    }

    static class JoinResult {
        Event left;
        Event right;

        JoinResult(Event left, Event right) {
            this.left = left;
            this.right = right;
        }

        @Override
        public String toString() {
            return String.format("Join[%s <-> %s]", left, right);
        }
    }

    static class WindowedStreamJoin {
        private final long windowSizeMs;
        // State stores: key -> list of events within window
        private final Map<String, Deque<Event>> leftStore = new ConcurrentHashMap<>();
        private final Map<String, Deque<Event>> rightStore = new ConcurrentHashMap<>();
        private final List<JoinResult> results = new ArrayList<>();

        WindowedStreamJoin(long windowSizeMs) {
            this.windowSizeMs = windowSizeMs;
        }

        public List<JoinResult> processLeft(Event event) {
            List<JoinResult> joined = new ArrayList<>();
            // Add to left store
            leftStore.computeIfAbsent(event.key, k -> new ArrayDeque<>()).add(event);
            // Probe right store for matching events within window
            Deque<Event> rightEvents = rightStore.get(event.key);
            if (rightEvents != null) {
                for (Event right : rightEvents) {
                    if (Math.abs(event.timestamp - right.timestamp) <= windowSizeMs) {
                        JoinResult result = new JoinResult(event, right);
                        joined.add(result);
                        results.add(result);
                    }
                }
            }
            evict(event.timestamp);
            return joined;
        }

        public List<JoinResult> processRight(Event event) {
            List<JoinResult> joined = new ArrayList<>();
            rightStore.computeIfAbsent(event.key, k -> new ArrayDeque<>()).add(event);
            Deque<Event> leftEvents = leftStore.get(event.key);
            if (leftEvents != null) {
                for (Event left : leftEvents) {
                    if (Math.abs(event.timestamp - left.timestamp) <= windowSizeMs) {
                        JoinResult result = new JoinResult(left, event);
                        joined.add(result);
                        results.add(result);
                    }
                }
            }
            evict(event.timestamp);
            return joined;
        }

        private void evict(long currentTime) {
            long cutoff = currentTime - windowSizeMs;
            evictStore(leftStore, cutoff);
            evictStore(rightStore, cutoff);
        }

        private void evictStore(Map<String, Deque<Event>> store, long cutoff) {
            store.forEach((key, deque) -> {
                while (!deque.isEmpty() && deque.peekFirst().timestamp < cutoff) {
                    deque.pollFirst();
                }
            });
            store.entrySet().removeIf(e -> e.getValue().isEmpty());
        }

        public List<JoinResult> getAllResults() {
            return results;
        }
    }

    public static void main(String[] args) {
        WindowedStreamJoin join = new WindowedStreamJoin(5000); // 5 second window

        // Simulate clickstream (left) and purchase events (right)
        System.out.println("=== Stream-Stream Windowed Join ===");
        System.out.println("Window size: 5000ms\n");

        // User clicks on product
        join.processLeft(new Event("user1", "click:productA", 1000));
        join.processLeft(new Event("user2", "click:productB", 2000));

        // User1 purchases within window
        List<JoinResult> results = join.processRight(new Event("user1", "purchase:productA", 3000));
        System.out.println("After user1 purchase at t=3000: " + results);

        // User2 purchases outside window
        results = join.processRight(new Event("user2", "purchase:productB", 9000));
        System.out.println("After user2 purchase at t=9000 (outside window): " + results);

        // Another click and immediate purchase
        join.processLeft(new Event("user3", "click:productC", 10000));
        results = join.processRight(new Event("user3", "purchase:productC", 10500));
        System.out.println("After user3 click+purchase within window: " + results);

        System.out.println("\nAll join results: " + join.getAllResults().size());
    }
}
