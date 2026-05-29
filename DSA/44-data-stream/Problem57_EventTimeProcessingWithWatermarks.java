import java.util.*;

/**
 * Problem 57: Event Time Processing with Watermarks
 * 
 * Production Relevance:
 * - Event time vs processing time: events arrive out of order due to network delays
 * - Watermarks signal "no more events before time T" enabling window closure
 * - Core concept in Apache Flink, Spark Structured Streaming, Google Dataflow
 * - Without watermarks: either wait forever or produce incorrect aggregations
 * 
 * Architect Considerations:
 * - Watermark strategies: periodic (max seen - allowed lateness), punctuated (special events)
 * - Too aggressive watermark = data loss; too conservative = high latency
 * - Allowed lateness + side output for late events arriving after watermark
 * - Watermark propagation in multi-source pipelines: min(watermarks) across partitions
 */
public class Problem57_EventTimeProcessingWithWatermarks {

    static class TimestampedEvent {
        String key;
        double value;
        long eventTime;

        TimestampedEvent(String key, double value, long eventTime) {
            this.key = key;
            this.value = value;
            this.eventTime = eventTime;
        }
    }

    static class WatermarkGenerator {
        private long maxTimestampSeen = Long.MIN_VALUE;
        private final long maxOutOfOrderness; // allowed lateness

        WatermarkGenerator(long maxOutOfOrderness) {
            this.maxOutOfOrderness = maxOutOfOrderness;
        }

        public void observeEvent(TimestampedEvent event) {
            maxTimestampSeen = Math.max(maxTimestampSeen, event.eventTime);
        }

        public long getCurrentWatermark() {
            return maxTimestampSeen - maxOutOfOrderness;
        }
    }

    static class WindowedAggregator {
        private final long windowSize;
        private final WatermarkGenerator watermarkGen;
        private final Map<Long, Map<String, Double>> openWindows = new TreeMap<>();
        private final List<String> closedResults = new ArrayList<>();
        private final List<TimestampedEvent> lateEvents = new ArrayList<>();
        private final long allowedLateness;

        WindowedAggregator(long windowSize, long maxOutOfOrderness, long allowedLateness) {
            this.windowSize = windowSize;
            this.watermarkGen = new WatermarkGenerator(maxOutOfOrderness);
            this.allowedLateness = allowedLateness;
        }

        public void processEvent(TimestampedEvent event) {
            watermarkGen.observeEvent(event);
            long windowStart = (event.eventTime / windowSize) * windowSize;
            long watermark = watermarkGen.getCurrentWatermark();

            // Check if event is late (after watermark + allowed lateness passed its window)
            if (windowStart + windowSize < watermark - allowedLateness) {
                lateEvents.add(event);
                return;
            }

            openWindows.computeIfAbsent(windowStart, k -> new HashMap<>())
                    .merge(event.key, event.value, Double::sum);

            // Close windows that watermark has passed
            Iterator<Map.Entry<Long, Map<String, Double>>> it = openWindows.entrySet().iterator();
            while (it.hasNext()) {
                Map.Entry<Long, Map<String, Double>> entry = it.next();
                if (entry.getKey() + windowSize <= watermark) {
                    closedResults.add(String.format("Window[%d-%d]: %s",
                            entry.getKey(), entry.getKey() + windowSize, entry.getValue()));
                    it.remove();
                }
            }
        }

        public List<String> getClosedResults() { return closedResults; }
        public List<TimestampedEvent> getLateEvents() { return lateEvents; }
        public int getOpenWindowCount() { return openWindows.size(); }
    }

    public static void main(String[] args) {
        System.out.println("=== Event Time Processing with Watermarks ===\n");

        // Window: 10s, max out-of-orderness: 3s, allowed lateness: 2s
        WindowedAggregator agg = new WindowedAggregator(10000, 3000, 2000);

        // Events arriving out of order
        TimestampedEvent[] events = {
            new TimestampedEvent("sensor1", 10.0, 1000),   // window [0-10000]
            new TimestampedEvent("sensor1", 20.0, 5000),   // window [0-10000]
            new TimestampedEvent("sensor1", 30.0, 12000),  // window [10000-20000]
            new TimestampedEvent("sensor1", 5.0,  3000),   // out of order, still in [0-10000]
            new TimestampedEvent("sensor1", 40.0, 15000),  // window [10000-20000], advances watermark to 12000
            new TimestampedEvent("sensor1", 50.0, 25000),  // advances watermark to 22000, closes [0-10000]
            new TimestampedEvent("sensor1", 1.0,  2000),   // LATE: window [0-10000] already closed
        };

        for (TimestampedEvent e : events) {
            System.out.printf("Process: key=%s, val=%.0f, eventTime=%d%n", e.key, e.value, e.eventTime);
            agg.processEvent(e);
        }

        System.out.println("\n--- Closed Windows ---");
        agg.getClosedResults().forEach(System.out::println);
        System.out.println("\nLate events (sent to side output): " + agg.getLateEvents().size());
        System.out.println("Open windows still buffered: " + agg.getOpenWindowCount());
    }
}
