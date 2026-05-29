import java.util.*;
import java.util.function.*;

/**
 * Problem 61: Global Window with Custom Triggers
 * 
 * Production Relevance:
 * - Global windows accumulate all events; triggers define WHEN to emit results
 * - Enables complex patterns: emit every N events, on timer, on specific condition
 * - Used for batch-within-stream patterns, accumulating aggregates, session-like behavior
 * - Apache Beam/Flink trigger model: FIRE, FIRE_AND_PURGE, CONTINUE
 * 
 * Architect Considerations:
 * - Without purging, state grows unbounded in global windows
 * - Composite triggers: AfterCount(100) OR AfterProcessingTime(30s)
 * - Early firings for speculative results, final firing for correctness
 */
public class Problem61_GlobalWindowCustomTriggers {

    static class Event {
        String key;
        double value;
        long timestamp;
        Event(String key, double value, long timestamp) {
            this.key = key; this.value = value; this.timestamp = timestamp;
        }
    }

    enum TriggerAction { CONTINUE, FIRE, FIRE_AND_PURGE }

    interface Trigger {
        TriggerAction onElement(Event event, TriggerContext ctx);
        TriggerAction onTimer(long time, TriggerContext ctx);
    }

    static class TriggerContext {
        int elementCount;
        long firstElementTime;
        long lastElementTime;
        double accumulatedValue;
    }

    // Count-based trigger
    static class CountTrigger implements Trigger {
        private final int threshold;
        CountTrigger(int threshold) { this.threshold = threshold; }

        public TriggerAction onElement(Event event, TriggerContext ctx) {
            return ctx.elementCount >= threshold ? TriggerAction.FIRE_AND_PURGE : TriggerAction.CONTINUE;
        }
        public TriggerAction onTimer(long time, TriggerContext ctx) { return TriggerAction.CONTINUE; }
    }

    // Timer-based trigger
    static class ProcessingTimeTrigger implements Trigger {
        private final long intervalMs;
        ProcessingTimeTrigger(long intervalMs) { this.intervalMs = intervalMs; }

        public TriggerAction onElement(Event event, TriggerContext ctx) { return TriggerAction.CONTINUE; }
        public TriggerAction onTimer(long time, TriggerContext ctx) {
            return (time - ctx.firstElementTime >= intervalMs && ctx.elementCount > 0)
                    ? TriggerAction.FIRE_AND_PURGE : TriggerAction.CONTINUE;
        }
    }

    // Delta trigger: fire when accumulated value exceeds threshold
    static class DeltaTrigger implements Trigger {
        private final double threshold;
        DeltaTrigger(double threshold) { this.threshold = threshold; }

        public TriggerAction onElement(Event event, TriggerContext ctx) {
            return ctx.accumulatedValue >= threshold ? TriggerAction.FIRE_AND_PURGE : TriggerAction.CONTINUE;
        }
        public TriggerAction onTimer(long time, TriggerContext ctx) { return TriggerAction.CONTINUE; }
    }

    // Composite: OR trigger
    static class OrTrigger implements Trigger {
        private final Trigger[] triggers;
        OrTrigger(Trigger... triggers) { this.triggers = triggers; }

        public TriggerAction onElement(Event event, TriggerContext ctx) {
            for (Trigger t : triggers) {
                TriggerAction a = t.onElement(event, ctx);
                if (a != TriggerAction.CONTINUE) return a;
            }
            return TriggerAction.CONTINUE;
        }
        public TriggerAction onTimer(long time, TriggerContext ctx) {
            for (Trigger t : triggers) {
                TriggerAction a = t.onTimer(time, ctx);
                if (a != TriggerAction.CONTINUE) return a;
            }
            return TriggerAction.CONTINUE;
        }
    }

    static class GlobalWindowProcessor {
        private final Trigger trigger;
        private final Map<String, List<Event>> state = new HashMap<>();
        private final Map<String, TriggerContext> contexts = new HashMap<>();
        private final List<String> emissions = new ArrayList<>();

        GlobalWindowProcessor(Trigger trigger) { this.trigger = trigger; }

        public void processEvent(Event event) {
            state.computeIfAbsent(event.key, k -> new ArrayList<>()).add(event);
            TriggerContext ctx = contexts.computeIfAbsent(event.key, k -> new TriggerContext());
            ctx.elementCount++;
            ctx.accumulatedValue += event.value;
            if (ctx.firstElementTime == 0) ctx.firstElementTime = event.timestamp;
            ctx.lastElementTime = event.timestamp;

            TriggerAction action = trigger.onElement(event, ctx);
            handleAction(event.key, action);
        }

        public void advanceProcessingTime(long time) {
            for (String key : new ArrayList<>(contexts.keySet())) {
                TriggerAction action = trigger.onTimer(time, contexts.get(key));
                handleAction(key, action);
            }
        }

        private void handleAction(String key, TriggerAction action) {
            if (action == TriggerAction.FIRE || action == TriggerAction.FIRE_AND_PURGE) {
                TriggerContext ctx = contexts.get(key);
                emissions.add(String.format("FIRE[%s]: count=%d, sum=%.1f", key, ctx.elementCount, ctx.accumulatedValue));
                if (action == TriggerAction.FIRE_AND_PURGE) {
                    state.remove(key);
                    contexts.remove(key);
                }
            }
        }

        public List<String> getEmissions() { return emissions; }
    }

    public static void main(String[] args) {
        System.out.println("=== Global Window with Custom Triggers ===\n");

        // Fire every 3 events OR when sum > 100
        Trigger composite = new OrTrigger(new CountTrigger(3), new DeltaTrigger(100));
        GlobalWindowProcessor proc = new GlobalWindowProcessor(composite);

        Event[] events = {
            new Event("A", 10, 1000),
            new Event("A", 20, 2000),
            new Event("A", 30, 3000),  // count=3, fires
            new Event("B", 150, 4000), // sum>100, fires immediately
            new Event("A", 5, 5000),
            new Event("A", 6, 6000),
            new Event("A", 7, 7000),   // count=3 again, fires
        };

        for (Event e : events) {
            proc.processEvent(e);
            System.out.printf("Event: key=%s val=%.0f%n", e.key, e.value);
        }

        System.out.println("\nEmissions:");
        proc.getEmissions().forEach(e -> System.out.println("  " + e));
    }
}
