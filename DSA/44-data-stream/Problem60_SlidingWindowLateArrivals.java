import java.util.*;

/**
 * Problem 60: Sliding Window with Late Arrivals
 * 
 * Production Relevance:
 * - Sliding windows emit results more frequently than tumbling (overlap)
 * - Late arrivals require retracting previous results and emitting corrections
 * - Used in real-time dashboards, alerting systems, SLA monitoring
 * - Tradeoff: freshness vs accuracy when late events arrive
 * 
 * Architect Considerations:
 * - Each event belongs to multiple overlapping windows
 * - State: O(windowSize/slideInterval) windows active simultaneously
 * - Retraction/correction model for downstream consumers
 */
public class Problem60_SlidingWindowLateArrivals {

    static class Event {
        String key;
        double value;
        long eventTime;
        Event(String key, double value, long eventTime) {
            this.key = key; this.value = value; this.eventTime = eventTime;
        }
    }

    static class WindowResult {
        long windowStart, windowEnd;
        double sum;
        int count;
        boolean isRetraction; // true = undo previous emission

        WindowResult(long start, long end, double sum, int count, boolean retraction) {
            this.windowStart = start; this.windowEnd = end;
            this.sum = sum; this.count = count; this.isRetraction = retraction;
        }

        @Override
        public String toString() {
            return String.format("%s Window[%d-%d] sum=%.1f count=%d",
                    isRetraction ? "RETRACT" : "EMIT", windowStart, windowEnd, sum, count);
        }
    }

    static class SlidingWindowProcessor {
        private final long windowSize;
        private final long slideInterval;
        private final long allowedLateness;
        // windowStart -> events in that window
        private final Map<Long, List<Event>> windowState = new TreeMap<>();
        // Track emitted results for retraction
        private final Map<Long, WindowResult> emittedResults = new HashMap<>();
        private long currentWatermark = Long.MIN_VALUE;

        SlidingWindowProcessor(long windowSize, long slideInterval, long allowedLateness) {
            this.windowSize = windowSize;
            this.slideInterval = slideInterval;
            this.allowedLateness = allowedLateness;
        }

        public List<WindowResult> processEvent(Event event) {
            List<WindowResult> results = new ArrayList<>();
            currentWatermark = Math.max(currentWatermark, event.eventTime - allowedLateness);

            // Determine which windows this event belongs to
            long firstWindowStart = ((event.eventTime - windowSize) / slideInterval + 1) * slideInterval;
            for (long wStart = firstWindowStart; wStart <= event.eventTime; wStart += slideInterval) {
                long wEnd = wStart + windowSize;
                if (event.eventTime >= wStart && event.eventTime < wEnd) {
                    windowState.computeIfAbsent(wStart, k -> new ArrayList<>()).add(event);

                    // If this window was already emitted, retract and re-emit
                    if (emittedResults.containsKey(wStart)) {
                        results.add(new WindowResult(wStart, wEnd,
                                emittedResults.get(wStart).sum, emittedResults.get(wStart).count, true));
                        WindowResult updated = computeWindow(wStart);
                        results.add(updated);
                        emittedResults.put(wStart, updated);
                    }
                }
            }

            // Close windows past watermark
            Iterator<Map.Entry<Long, List<Event>>> it = windowState.entrySet().iterator();
            while (it.hasNext()) {
                Map.Entry<Long, List<Event>> entry = it.next();
                long wEnd = entry.getKey() + windowSize;
                if (wEnd <= currentWatermark && !emittedResults.containsKey(entry.getKey())) {
                    WindowResult result = computeWindow(entry.getKey());
                    results.add(result);
                    emittedResults.put(entry.getKey(), result);
                }
            }
            return results;
        }

        private WindowResult computeWindow(long windowStart) {
            List<Event> events = windowState.getOrDefault(windowStart, Collections.emptyList());
            double sum = events.stream().mapToDouble(e -> e.value).sum();
            return new WindowResult(windowStart, windowStart + windowSize, sum, events.size(), false);
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Sliding Window with Late Arrivals ===\n");

        // Window: 10s, slide: 5s, allowed lateness: 3s
        SlidingWindowProcessor proc = new SlidingWindowProcessor(10000, 5000, 3000);

        Event[] events = {
            new Event("s1", 10, 1000),
            new Event("s1", 20, 6000),
            new Event("s1", 30, 11000),
            new Event("s1", 40, 16000),  // watermark advances, closes early windows
            new Event("s1", 5,  3000),   // LATE arrival, triggers retraction
        };

        for (Event e : events) {
            System.out.printf("Input: value=%.0f eventTime=%d%n", e.value, e.eventTime);
            List<WindowResult> results = proc.processEvent(e);
            for (WindowResult r : results) {
                System.out.println("  " + r);
            }
        }
    }
}
