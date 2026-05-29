import java.util.*;

/**
 * Problem 58: Out-of-Order Event Handling
 * 
 * Production Relevance:
 * - Network partitions, retries, multi-path routing cause events to arrive out of order
 * - Must reconstruct correct ordering for stateful processing (e.g., sequence of user actions)
 * - Techniques: buffering + sorting, sequence numbers, vector clocks
 * - Used in real-time analytics, event sourcing, distributed tracing correlation
 * 
 * Architect Considerations:
 * - Buffer size vs latency tradeoff: larger buffer = more correct but higher latency
 * - Sequence gaps: wait for missing events or emit with best-effort ordering
 * - Per-key ordering may be sufficient (relaxed global ordering)
 */
public class Problem58_OutOfOrderEventHandling {

    static class SequencedEvent {
        String key;
        long sequenceNumber;
        String payload;
        long eventTime;

        SequencedEvent(String key, long seq, String payload, long eventTime) {
            this.key = key;
            this.sequenceNumber = seq;
            this.payload = payload;
            this.eventTime = eventTime;
        }

        @Override
        public String toString() {
            return String.format("[seq=%d] %s", sequenceNumber, payload);
        }
    }

    // Per-key reordering buffer using sequence numbers
    static class SequenceReorderBuffer {
        private final Map<String, TreeMap<Long, SequencedEvent>> buffers = new HashMap<>();
        private final Map<String, Long> nextExpectedSeq = new HashMap<>();
        private final long maxWaitMs;
        private final Map<String, Long> lastEmitTime = new HashMap<>();
        private final List<SequencedEvent> emitted = new ArrayList<>();
        private final List<SequencedEvent> droppedOld = new ArrayList<>();

        SequenceReorderBuffer(long maxWaitMs) {
            this.maxWaitMs = maxWaitMs;
        }

        public List<SequencedEvent> onEvent(SequencedEvent event, long processingTime) {
            List<SequencedEvent> result = new ArrayList<>();
            String key = event.key;
            long expected = nextExpectedSeq.getOrDefault(key, 1L);

            // Drop events older than already emitted
            if (event.sequenceNumber < expected) {
                droppedOld.add(event);
                return result;
            }

            // Buffer the event
            buffers.computeIfAbsent(key, k -> new TreeMap<>()).put(event.sequenceNumber, event);

            // Emit consecutive events starting from expected
            TreeMap<Long, SequencedEvent> buf = buffers.get(key);
            while (buf.containsKey(expected)) {
                SequencedEvent emit = buf.remove(expected);
                result.add(emit);
                emitted.add(emit);
                expected++;
            }
            nextExpectedSeq.put(key, expected);
            lastEmitTime.put(key, processingTime);

            // Timeout: force emit if waited too long for gap
            if (!buf.isEmpty()) {
                Long lastEmit = lastEmitTime.getOrDefault(key, 0L);
                if (processingTime - lastEmit > maxWaitMs) {
                    // Skip the gap, emit what we have
                    Map.Entry<Long, SequencedEvent> first = buf.firstEntry();
                    while (first != null && first.getKey() > expected) {
                        expected = first.getKey(); // Jump over gap
                        SequencedEvent emit = buf.remove(expected);
                        result.add(emit);
                        emitted.add(emit);
                        expected++;
                        first = buf.firstEntry();
                    }
                    nextExpectedSeq.put(key, expected);
                }
            }
            return result;
        }

        public int getBufferSize(String key) {
            TreeMap<Long, SequencedEvent> buf = buffers.get(key);
            return buf == null ? 0 : buf.size();
        }

        public List<SequencedEvent> getEmitted() { return emitted; }
        public List<SequencedEvent> getDropped() { return droppedOld; }
    }

    public static void main(String[] args) {
        System.out.println("=== Out-of-Order Event Handling ===\n");

        SequenceReorderBuffer buffer = new SequenceReorderBuffer(5000);

        // Events arriving out of order for user1
        SequencedEvent[] events = {
            new SequencedEvent("user1", 1, "login", 100),
            new SequencedEvent("user1", 3, "add_to_cart", 300),   // seq 2 missing
            new SequencedEvent("user1", 2, "browse_product", 200), // arrives late
            new SequencedEvent("user1", 5, "checkout", 500),       // seq 4 missing
            new SequencedEvent("user1", 4, "apply_coupon", 400),   // fills gap
            new SequencedEvent("user1", 1, "login", 100),          // duplicate (old)
        };

        long processingTime = 1000;
        for (SequencedEvent e : events) {
            List<SequencedEvent> emitted = buffer.onEvent(e, processingTime);
            System.out.printf("Received %s -> Emitted: %s (buffered: %d)%n",
                    e, emitted, buffer.getBufferSize("user1"));
            processingTime += 100;
        }

        System.out.println("\nFinal emitted order:");
        buffer.getEmitted().forEach(e -> System.out.println("  " + e));
        System.out.println("Dropped (old): " + buffer.getDropped().size());
    }
}
