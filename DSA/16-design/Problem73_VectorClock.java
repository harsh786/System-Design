import java.util.*;

/**
 * Problem 73: Vector Clock for Causality Tracking
 * 
 * PRODUCTION MAPPING: DynamoDB (simplified), Riak, Voldemort,
 *                     CRDTs, distributed debugging (Lamport clocks ancestor)
 * 
 * Problem: In distributed systems, physical clocks are unreliable.
 * Need logical mechanism to determine causal ordering of events.
 * 
 * Vector Clock: array of counters, one per node
 * - VC[i] = number of events node i knows about
 * - On local event: VC[self]++
 * - On send: attach VC to message
 * - On receive: VC = max(local_VC, received_VC); VC[self]++
 * 
 * Comparison:
 * - A < B (A happened-before B): A[i] <= B[i] for all i, AND A != B
 * - A || B (concurrent): neither A < B nor B < A
 * 
 * Trade-offs:
 * - Size grows with number of nodes (O(N) per event)
 * - DynamoDB uses simplified version clocks (prune old entries)
 * - Interval tree clocks solve the growth problem
 */
public class Problem73_VectorClock {

    static class VectorClock {
        private final Map<String, Integer> clock;

        public VectorClock() {
            this.clock = new HashMap<>();
        }

        public VectorClock(Map<String, Integer> clock) {
            this.clock = new HashMap<>(clock);
        }

        /** Increment for a local event */
        public void increment(String nodeId) {
            clock.merge(nodeId, 1, Integer::sum);
        }

        /** Merge with another clock (take max of each component) */
        public void merge(VectorClock other) {
            for (Map.Entry<String, Integer> e : other.clock.entrySet()) {
                clock.merge(e.getKey(), e.getValue(), Integer::max);
            }
        }

        /** Send event: increment self, return copy to attach to message */
        public VectorClock send(String nodeId) {
            increment(nodeId);
            return copy();
        }

        /** Receive event: merge with received clock, then increment self */
        public void receive(String nodeId, VectorClock received) {
            merge(received);
            increment(nodeId);
        }

        public int get(String nodeId) {
            return clock.getOrDefault(nodeId, 0);
        }

        public VectorClock copy() {
            return new VectorClock(this.clock);
        }

        /**
         * Compare two vector clocks:
         * -1: this happened-before other
         *  1: other happened-before this
         *  0: concurrent (neither dominates)
         */
        public int compareTo(VectorClock other) {
            Set<String> allNodes = new HashSet<>(this.clock.keySet());
            allNodes.addAll(other.clock.keySet());

            boolean thisLeq = true;  // this <= other
            boolean otherLeq = true; // other <= this

            for (String node : allNodes) {
                int thisVal = this.get(node);
                int otherVal = other.get(node);
                if (thisVal > otherVal) otherLeq = false;
                if (otherVal > thisVal) thisLeq = false;
            }

            if (thisLeq && otherLeq) return 0; // equal
            if (thisLeq) return -1;  // this < other
            if (otherLeq) return 1;  // this > other
            return 0; // concurrent
        }

        public boolean happenedBefore(VectorClock other) { return compareTo(other) == -1; }
        public boolean isConcurrentWith(VectorClock other) {
            return compareTo(other) == 0 && !this.clock.equals(other.clock);
        }

        @Override
        public String toString() { return clock.toString(); }
        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (!(o instanceof VectorClock)) return false;
            return clock.equals(((VectorClock) o).clock);
        }
    }

    /** Simulates a distributed node that tracks causality */
    static class DistributedNode {
        final String id;
        VectorClock clock = new VectorClock();
        final List<String> eventHistory = new ArrayList<>();

        DistributedNode(String id) { this.id = id; }

        VectorClock localEvent(String description) {
            clock.increment(id);
            eventHistory.add(description + " " + clock);
            return clock.copy();
        }

        VectorClock sendMessage(String description) {
            VectorClock msgClock = clock.send(id);
            eventHistory.add("SEND " + description + " " + clock);
            return msgClock;
        }

        VectorClock receiveMessage(VectorClock received, String description) {
            clock.receive(id, received);
            eventHistory.add("RECV " + description + " " + clock);
            return clock.copy();
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Vector Clock for Causality Tracking ===\n");

        // Test 1: Basic ordering
        VectorClock a = new VectorClock();
        a.increment("A");  // {A:1}
        
        VectorClock b = new VectorClock();
        b.increment("A");  // {A:1}
        b.increment("A");  // {A:2}
        
        assert a.happenedBefore(b) : "a={A:1} should be before b={A:2}";
        System.out.println("PASS: " + a + " happened-before " + b);

        // Test 2: Concurrent events
        VectorClock c1 = new VectorClock();
        c1.increment("A");  // {A:1}
        
        VectorClock c2 = new VectorClock();
        c2.increment("B");  // {B:1}
        
        assert c1.isConcurrentWith(c2) : "Should be concurrent";
        assert !c1.happenedBefore(c2);
        assert !c2.happenedBefore(c1);
        System.out.println("PASS: " + c1 + " || " + c2 + " (concurrent)");

        // Test 3: Message passing establishes causality
        DistributedNode nodeA = new DistributedNode("A");
        DistributedNode nodeB = new DistributedNode("B");
        DistributedNode nodeC = new DistributedNode("C");

        // A does local work
        VectorClock e1 = nodeA.localEvent("write x=1");
        // A sends message to B
        VectorClock msgClock = nodeA.sendMessage("update x");
        // B receives and does work
        VectorClock e2 = nodeB.receiveMessage(msgClock, "from A");
        VectorClock e3 = nodeB.localEvent("process x");

        assert e1.happenedBefore(e3) : "A's event should causally precede B's processing";
        System.out.println("PASS: Message send establishes causal order");

        // Test 4: Detecting conflicting writes (like DynamoDB)
        nodeA = new DistributedNode("A");
        nodeB = new DistributedNode("B");

        // Both write to same key without communicating
        VectorClock writeA = nodeA.localEvent("write key=valueA");
        VectorClock writeB = nodeB.localEvent("write key=valueB");

        assert writeA.isConcurrentWith(writeB);
        System.out.println("PASS: Concurrent writes detected (conflict!) " + writeA + " || " + writeB);
        System.out.println("  -> Application must resolve conflict (LWW, merge, user choice)");

        // Test 5: Causal chain across 3 nodes
        nodeA = new DistributedNode("A");
        nodeB = new DistributedNode("B");
        nodeC = new DistributedNode("C");

        VectorClock m1 = nodeA.sendMessage("to B");
        nodeB.receiveMessage(m1, "from A");
        VectorClock m2 = nodeB.sendMessage("to C");
        VectorClock finalC = nodeC.receiveMessage(m2, "from B");

        // A's original event should causally precede C's event
        assert nodeA.clock.happenedBefore(finalC);
        System.out.println("PASS: Transitive causality: A -> B -> C");
        System.out.println("  A: " + nodeA.clock);
        System.out.println("  B: " + nodeB.clock);
        System.out.println("  C: " + nodeC.clock);

        // Test 6: Merge (like receiving multiple replicas)
        VectorClock replica1 = new VectorClock();
        replica1.increment("A"); replica1.increment("A"); // {A:2}
        
        VectorClock replica2 = new VectorClock();
        replica2.increment("B"); replica2.increment("B"); replica2.increment("B"); // {B:3}

        VectorClock merged = replica1.copy();
        merged.merge(replica2);
        assert merged.get("A") == 2 && merged.get("B") == 3;
        System.out.println("PASS: Merge takes component-wise max: " + merged);

        // Test 7: Event history
        System.out.println("\nNode B event history:");
        for (String event : nodeB.eventHistory) {
            System.out.println("  " + event);
        }

        System.out.println("\nAll tests passed!");
    }
}
