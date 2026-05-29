import java.util.*;

/**
 * Problem 59: Causal Ordering in Distributed System
 * 
 * Production Relevance:
 * - Vector clocks / Lamport timestamps establish happened-before relationships
 * - Causal consistency: if A causes B, all observers see A before B
 * - Used in distributed databases (Dynamo, Riak), CRDTs, collaborative editing
 * - Weaker than total ordering but stronger than eventual consistency
 * 
 * Architect Considerations:
 * - Vector clock size grows with number of nodes (O(N) per message)
 * - Dotted version vectors optimize for client-server architectures
 * - Causal delivery: buffer messages until causal dependencies satisfied
 */
public class Problem59_CausalOrderingDistributedSystem {

    static class VectorClock {
        Map<String, Integer> clock = new HashMap<>();

        VectorClock() {}
        VectorClock(VectorClock other) { this.clock = new HashMap<>(other.clock); }

        void increment(String nodeId) { clock.merge(nodeId, 1, Integer::sum); }

        void merge(VectorClock other) {
            for (Map.Entry<String, Integer> e : other.clock.entrySet()) {
                clock.merge(e.getKey(), e.getValue(), Math::max);
            }
        }

        // Returns: -1 (this before other), 1 (this after other), 0 (concurrent)
        int compareTo(VectorClock other) {
            boolean thisLessOrEqual = true, otherLessOrEqual = true;
            Set<String> allKeys = new HashSet<>(clock.keySet());
            allKeys.addAll(other.clock.keySet());

            for (String key : allKeys) {
                int a = clock.getOrDefault(key, 0);
                int b = other.clock.getOrDefault(key, 0);
                if (a > b) otherLessOrEqual = false;
                if (b > a) thisLessOrEqual = false;
            }

            if (thisLessOrEqual && !otherLessOrEqual) return -1; // this happened before other
            if (otherLessOrEqual && !thisLessOrEqual) return 1;  // this happened after other
            if (thisLessOrEqual && otherLessOrEqual) return -1;  // equal (treat as before)
            return 0; // concurrent
        }

        @Override
        public String toString() { return clock.toString(); }
    }

    static class CausalMessage {
        String sender;
        String content;
        VectorClock timestamp;

        CausalMessage(String sender, String content, VectorClock ts) {
            this.sender = sender; this.content = content; this.timestamp = new VectorClock(ts);
        }
    }

    static class CausalNode {
        String id;
        VectorClock clock = new VectorClock();
        List<CausalMessage> deliveryBuffer = new ArrayList<>();
        List<CausalMessage> delivered = new ArrayList<>();

        CausalNode(String id) { this.id = id; }

        CausalMessage send(String content) {
            clock.increment(id);
            CausalMessage msg = new CausalMessage(id, content, clock);
            delivered.add(msg);
            return msg;
        }

        void receive(CausalMessage msg) {
            deliveryBuffer.add(msg);
            deliverReady();
        }

        private void deliverReady() {
            boolean progress = true;
            while (progress) {
                progress = false;
                Iterator<CausalMessage> it = deliveryBuffer.iterator();
                while (it.hasNext()) {
                    CausalMessage msg = it.next();
                    if (canDeliver(msg)) {
                        clock.merge(msg.timestamp);
                        clock.increment(id);
                        delivered.add(msg);
                        it.remove();
                        progress = true;
                    }
                }
            }
        }

        private boolean canDeliver(CausalMessage msg) {
            // Can deliver if our clock >= msg.timestamp for all entries except sender
            for (Map.Entry<String, Integer> e : msg.timestamp.clock.entrySet()) {
                if (e.getKey().equals(msg.sender)) {
                    // For sender, we need exactly one less (this is the next message from them)
                    if (clock.clock.getOrDefault(e.getKey(), 0) < e.getValue() - 1) return false;
                } else {
                    if (clock.clock.getOrDefault(e.getKey(), 0) < e.getValue()) return false;
                }
            }
            return true;
        }

        public List<String> getDeliveredContents() {
            List<String> result = new ArrayList<>();
            for (CausalMessage m : delivered) result.add(m.sender + ":" + m.content);
            return result;
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Causal Ordering in Distributed System ===\n");

        CausalNode alice = new CausalNode("alice");
        CausalNode bob = new CausalNode("bob");
        CausalNode carol = new CausalNode("carol");

        // Alice sends m1
        CausalMessage m1 = alice.send("Hello everyone!");
        System.out.println("Alice sends: " + m1.content + " VC=" + m1.timestamp);

        // Bob receives m1, then replies
        bob.receive(m1);
        CausalMessage m2 = bob.send("Hi Alice!");
        System.out.println("Bob sends: " + m2.content + " VC=" + m2.timestamp);

        // Carol receives m2 BEFORE m1 (out of order network)
        carol.receive(m2); // Should be buffered (causal dep on m1 not met)
        System.out.println("\nCarol receives m2 before m1:");
        System.out.println("  Delivered: " + carol.getDeliveredContents());
        System.out.println("  Buffered: " + carol.deliveryBuffer.size());

        // Carol now receives m1
        carol.receive(m1); // Now both can be delivered in causal order
        System.out.println("\nCarol receives m1:");
        System.out.println("  Delivered: " + carol.getDeliveredContents());
        System.out.println("  Buffered: " + carol.deliveryBuffer.size());

        // Concurrent messages (no causal relationship)
        CausalMessage m3 = alice.send("Anyone free for lunch?");
        CausalMessage m4 = bob.send("Meeting at 3pm");
        int comparison = m3.timestamp.compareTo(m4.timestamp);
        System.out.printf("%nAlice's m3 vs Bob's m4: %s%n",
                comparison == 0 ? "CONCURRENT" : comparison < 0 ? "m3 before m4" : "m4 before m3");
    }
}
