import java.util.*;

/**
 * Problem 74: Conflict-Free Replicated Data Types (G-Counter, PN-Counter)
 * 
 * PRODUCTION MAPPING: Redis CRDT (Active-Active), Riak, SoundCloud (counters),
 *                     Phoenix/Elixir (LiveView), Apple Notes (collaboration),
 *                     Figma (multiplayer), Automerge, Yjs
 * 
 * Core Property: CRDTs can be updated independently and concurrently without
 * coordination, and always converge to the same state (Strong Eventual Consistency).
 * 
 * Types implemented:
 * 1. G-Counter (Grow-only counter): increment only, merge = max per node
 * 2. PN-Counter (Positive-Negative): supports decrement via two G-Counters
 * 3. G-Set (Grow-only set): add only, merge = union
 * 4. OR-Set (Observed-Remove set): add and remove with unique tags
 * 
 * Why CRDTs matter for staff:
 * - Eliminate coordination (no consensus needed)
 * - Always available (AP in CAP)
 * - Eventual consistency guaranteed mathematically (not just hopefully)
 * 
 * Trade-offs:
 * - State-based CRDTs: send full state (larger messages, simpler)
 * - Op-based CRDTs: send operations (smaller messages, need reliable delivery)
 * - Limited operations (must be commutative, associative, idempotent after merge)
 */
public class Problem74_CRDT {

    // ======== G-Counter (Grow-only) ========
    static class GCounter {
        private final Map<String, Long> counts = new HashMap<>();
        private final String nodeId;

        GCounter(String nodeId) { this.nodeId = nodeId; }

        void increment() { increment(1); }
        void increment(long amount) {
            counts.merge(nodeId, amount, Long::sum);
        }

        long value() {
            return counts.values().stream().mapToLong(Long::longValue).sum();
        }

        /** Merge: take max of each node's count */
        void merge(GCounter other) {
            for (Map.Entry<String, Long> e : other.counts.entrySet()) {
                counts.merge(e.getKey(), e.getValue(), Long::max);
            }
        }

        GCounter copy(String newNodeId) {
            GCounter g = new GCounter(newNodeId);
            g.counts.putAll(this.counts);
            return g;
        }

        @Override public String toString() { return "GCounter" + counts + "=" + value(); }
    }

    // ======== PN-Counter (supports decrement) ========
    static class PNCounter {
        private final GCounter positive;
        private final GCounter negative;
        private final String nodeId;

        PNCounter(String nodeId) {
            this.nodeId = nodeId;
            this.positive = new GCounter(nodeId);
            this.negative = new GCounter(nodeId);
        }

        void increment() { positive.increment(); }
        void increment(long amount) { positive.increment(amount); }
        void decrement() { negative.increment(); }
        void decrement(long amount) { negative.increment(amount); }

        long value() { return positive.value() - negative.value(); }

        void merge(PNCounter other) {
            positive.merge(other.positive);
            negative.merge(other.negative);
        }

        @Override public String toString() { return "PNCounter{+" + positive.value() + "-" + negative.value() + "=" + value() + "}"; }
    }

    // ======== G-Set (Grow-only Set) ========
    static class GSet<T> {
        private final Set<T> elements = new HashSet<>();

        void add(T element) { elements.add(element); }
        boolean contains(T element) { return elements.contains(element); }
        Set<T> value() { return Collections.unmodifiableSet(elements); }

        void merge(GSet<T> other) { elements.addAll(other.elements); }

        @Override public String toString() { return "GSet" + elements; }
    }

    // ======== OR-Set (Observed-Remove Set) ========
    static class ORSet<T> {
        // Each element has a set of unique "add tags"
        private final Map<T, Set<String>> elements = new HashMap<>();
        private final Set<String> removedTags = new HashSet<>();
        private final String nodeId;
        private int tagCounter = 0;

        ORSet(String nodeId) { this.nodeId = nodeId; }

        void add(T element) {
            String tag = nodeId + ":" + (tagCounter++);
            elements.computeIfAbsent(element, k -> new HashSet<>()).add(tag);
        }

        void remove(T element) {
            Set<String> tags = elements.get(element);
            if (tags != null) {
                removedTags.addAll(tags);
                elements.remove(element);
            }
        }

        boolean contains(T element) {
            Set<String> tags = elements.get(element);
            if (tags == null) return false;
            // Remove any tags that have been removed
            tags.removeAll(removedTags);
            if (tags.isEmpty()) { elements.remove(element); return false; }
            return true;
        }

        Set<T> value() {
            Set<T> result = new HashSet<>();
            for (Map.Entry<T, Set<String>> e : elements.entrySet()) {
                Set<String> activeTags = new HashSet<>(e.getValue());
                activeTags.removeAll(removedTags);
                if (!activeTags.isEmpty()) result.add(e.getKey());
            }
            return result;
        }

        void merge(ORSet<T> other) {
            // Merge add tags
            for (Map.Entry<T, Set<String>> e : other.elements.entrySet()) {
                elements.computeIfAbsent(e.getKey(), k -> new HashSet<>()).addAll(e.getValue());
            }
            // Merge removed tags
            removedTags.addAll(other.removedTags);
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Conflict-Free Replicated Data Types (CRDTs) ===\n");

        // Test 1: G-Counter - concurrent increments converge
        System.out.println("--- G-Counter ---");
        GCounter counterA = new GCounter("A");
        GCounter counterB = new GCounter("B");
        GCounter counterC = new GCounter("C");

        counterA.increment(5);
        counterB.increment(3);
        counterC.increment(7);

        // Merge all (simulating gossip/replication)
        counterA.merge(counterB);
        counterA.merge(counterC);
        counterB.merge(counterA);
        counterC.merge(counterA);

        assert counterA.value() == 15 && counterB.value() == 15 && counterC.value() == 15;
        System.out.println("PASS: G-Counter converges to 15 on all replicas");

        // Test 2: G-Counter idempotent merge (same data merged twice)
        counterA.merge(counterB); // merge again - should not change
        assert counterA.value() == 15;
        System.out.println("PASS: Merge is idempotent");

        // Test 3: PN-Counter with decrements
        System.out.println("\n--- PN-Counter ---");
        PNCounter pnA = new PNCounter("A");
        PNCounter pnB = new PNCounter("B");

        pnA.increment(10);
        pnB.decrement(3);
        pnA.decrement(2);
        pnB.increment(5);

        pnA.merge(pnB);
        pnB.merge(pnA);

        assert pnA.value() == 10 : "Expected 10, got: " + pnA.value(); // 15 - 5
        assert pnB.value() == pnA.value();
        System.out.println("PASS: PN-Counter converges: " + pnA);

        // Test 4: G-Set
        System.out.println("\n--- G-Set ---");
        GSet<String> setA = new GSet<>();
        GSet<String> setB = new GSet<>();

        setA.add("item1");
        setA.add("item2");
        setB.add("item2");
        setB.add("item3");

        setA.merge(setB);
        assert setA.value().size() == 3;
        assert setA.contains("item1") && setA.contains("item2") && setA.contains("item3");
        System.out.println("PASS: G-Set union converges: " + setA);

        // Test 5: OR-Set - add/remove with concurrent operations
        System.out.println("\n--- OR-Set ---");
        ORSet<String> orA = new ORSet<>("A");
        ORSet<String> orB = new ORSet<>("B");

        orA.add("x");
        orA.add("y");
        orB.merge(orA); // B sees {x, y}

        // Concurrent: A removes x, B adds x again
        orA.remove("x");
        orB.add("x"); // new add with new tag

        // Merge
        orA.merge(orB);
        orB.merge(orA);

        // "Add wins" semantics: x should exist (B's add has new tag not in A's removes)
        assert orA.contains("x") : "OR-Set: concurrent add should win";
        System.out.println("PASS: OR-Set add-wins semantics (concurrent add/remove)");
        System.out.println("  Set contents: " + orA.value());

        // Test 6: OR-Set remove succeeds when no concurrent add
        ORSet<String> orC = new ORSet<>("C");
        orC.add("temp");
        assert orC.contains("temp");
        orC.remove("temp");
        assert !orC.contains("temp");
        System.out.println("PASS: OR-Set remove works without concurrent add");

        // Test 7: Real-world example - distributed page view counter
        System.out.println("\n--- Real-world: Distributed Page View Counter ---");
        GCounter dc1 = new GCounter("datacenter-us");
        GCounter dc2 = new GCounter("datacenter-eu");
        GCounter dc3 = new GCounter("datacenter-asia");

        // Each datacenter counts locally
        dc1.increment(1000000);
        dc2.increment(750000);
        dc3.increment(500000);

        // Periodic merge (e.g., every 5 seconds)
        dc1.merge(dc2); dc1.merge(dc3);
        System.out.println("  Total views (after merge): " + dc1.value());
        assert dc1.value() == 2250000;
        System.out.println("PASS: Multi-datacenter counter = " + dc1.value());

        // Test 8: Commutativity proof
        GCounter x = new GCounter("X"); x.increment(5);
        GCounter y = new GCounter("Y"); y.increment(3);
        
        GCounter xy = new GCounter("test"); xy.counts.putAll(x.counts); xy.merge(y);
        GCounter yx = new GCounter("test"); yx.counts.putAll(y.counts); yx.merge(x);
        assert xy.value() == yx.value();
        System.out.println("\nPASS: Merge is commutative (x⊕y = y⊕x)");

        System.out.println("\nAll tests passed!");
    }
}
