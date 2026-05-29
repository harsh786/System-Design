import java.util.*;
import java.security.*;
import java.nio.charset.*;

/**
 * Problem 53: Consistent Hash Ring with Virtual Nodes
 * 
 * PRODUCTION MAPPING: DynamoDB partitioning, Cassandra token ring, Redis Cluster,
 *                     Memcached (ketama), Nginx upstream hashing
 * 
 * Design Decisions:
 * - Virtual nodes (vnodes) solve the uneven distribution problem
 * - MD5 hashing for uniform distribution across ring
 * - TreeMap as the ring (sorted map, O(log n) ceiling lookup)
 * 
 * Trade-offs:
 * - More vnodes = better distribution but more memory (150-200 vnodes/node typical)
 * - MD5 is not cryptographically needed but gives good distribution
 * - Adding/removing nodes only redistributes K/N keys (K=keys, N=nodes)
 * 
 * Complexity:
 * - Lookup: O(log(N * vnodes)) where N = physical nodes
 * - Add/Remove node: O(vnodes * log(N * vnodes))
 * 
 * Key insight for staff interviews: Without vnodes, adding a node only offloads
 * its clockwise neighbor. With vnodes, load is distributed from ALL nodes.
 */
public class Problem53_ConsistentHashRing {

    static class ConsistentHashRing<T> {
        private final TreeMap<Long, T> ring = new TreeMap<>();
        private final Map<T, Integer> nodeVnodeCount = new HashMap<>();
        private final int defaultVnodes;

        public ConsistentHashRing(int defaultVnodes) {
            this.defaultVnodes = defaultVnodes;
        }

        public void addNode(T node) {
            addNode(node, defaultVnodes);
        }

        public void addNode(T node, int vnodes) {
            nodeVnodeCount.put(node, vnodes);
            for (int i = 0; i < vnodes; i++) {
                long hash = hash(node.toString() + "#" + i);
                ring.put(hash, node);
            }
        }

        public void removeNode(T node) {
            Integer vnodes = nodeVnodeCount.remove(node);
            if (vnodes == null) return;
            for (int i = 0; i < vnodes; i++) {
                long hash = hash(node.toString() + "#" + i);
                ring.remove(hash);
            }
        }

        /**
         * Find the node responsible for a given key.
         * Walk clockwise on ring to find first node >= hash(key).
         */
        public T getNode(String key) {
            if (ring.isEmpty()) return null;
            long hash = hash(key);
            // Get the first entry with hash >= key hash (clockwise)
            Map.Entry<Long, T> entry = ring.ceilingEntry(hash);
            if (entry == null) {
                // Wrap around to first entry
                entry = ring.firstEntry();
            }
            return entry.getValue();
        }

        /**
         * Get N distinct nodes for replication (walk clockwise, skip duplicates)
         */
        public List<T> getNodes(String key, int count) {
            if (ring.isEmpty()) return Collections.emptyList();
            
            List<T> result = new ArrayList<>();
            Set<T> seen = new HashSet<>();
            long hash = hash(key);

            // Get tail map from hash position, then wrap around
            SortedMap<Long, T> tailMap = ring.tailMap(hash);
            for (T node : tailMap.values()) {
                if (seen.add(node)) {
                    result.add(node);
                    if (result.size() == count) return result;
                }
            }
            // Wrap around
            for (T node : ring.values()) {
                if (seen.add(node)) {
                    result.add(node);
                    if (result.size() == count) return result;
                }
            }
            return result;
        }

        public int getRingSize() { return ring.size(); }
        public Set<T> getPhysicalNodes() { return nodeVnodeCount.keySet(); }

        private long hash(String key) {
            try {
                MessageDigest md = MessageDigest.getInstance("MD5");
                byte[] digest = md.digest(key.getBytes(StandardCharsets.UTF_8));
                // Use first 8 bytes as long
                long h = 0;
                for (int i = 0; i < 8; i++) {
                    h = (h << 8) | (digest[i] & 0xFF);
                }
                return h;
            } catch (NoSuchAlgorithmException e) {
                throw new RuntimeException(e);
            }
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Consistent Hash Ring with Virtual Nodes ===\n");

        // Test 1: Basic routing
        ConsistentHashRing<String> ring = new ConsistentHashRing<>(150);
        ring.addNode("server-1");
        ring.addNode("server-2");
        ring.addNode("server-3");
        
        String node = ring.getNode("user:123");
        assert node != null;
        System.out.println("PASS: Key 'user:123' -> " + node);

        // Test 2: Consistency - same key always maps to same node
        String node1 = ring.getNode("session:abc");
        String node2 = ring.getNode("session:abc");
        assert node1.equals(node2) : "Same key must map to same node";
        System.out.println("PASS: Consistent mapping for same key");

        // Test 3: Minimal redistribution on node add
        Map<String, String> before = new HashMap<>();
        for (int i = 0; i < 10000; i++) {
            before.put("key:" + i, ring.getNode("key:" + i));
        }
        ring.addNode("server-4"); // Add new node
        int moved = 0;
        for (int i = 0; i < 10000; i++) {
            if (!before.get("key:" + i).equals(ring.getNode("key:" + i))) {
                moved++;
            }
        }
        double movedPct = moved * 100.0 / 10000;
        // Ideal: 1/4 = 25% keys should move (K/N)
        System.out.printf("PASS: %.1f%% keys redistributed (ideal ~25%%)\n", movedPct);
        assert movedPct < 35 : "Too many keys moved: " + movedPct + "%";

        // Test 4: Distribution uniformity
        ring = new ConsistentHashRing<>(150);
        ring.addNode("A");
        ring.addNode("B");
        ring.addNode("C");
        Map<String, Integer> distribution = new HashMap<>();
        for (int i = 0; i < 30000; i++) {
            String n = ring.getNode("item:" + i);
            distribution.merge(n, 1, Integer::sum);
        }
        System.out.println("Distribution: " + distribution);
        for (int count : distribution.values()) {
            double pct = count * 100.0 / 30000;
            assert pct > 20 && pct < 45 : "Uneven distribution: " + pct + "%";
        }
        System.out.println("PASS: Reasonably uniform distribution");

        // Test 5: Replication - get multiple nodes
        ring = new ConsistentHashRing<>(150);
        ring.addNode("node-1");
        ring.addNode("node-2");
        ring.addNode("node-3");
        List<String> replicas = ring.getNodes("data:xyz", 3);
        assert replicas.size() == 3 : "Should get 3 distinct nodes";
        assert new HashSet<>(replicas).size() == 3 : "All should be distinct";
        System.out.println("PASS: Replication returns 3 distinct nodes: " + replicas);

        // Test 6: Node removal
        ring.removeNode("node-2");
        String after = ring.getNode("data:xyz");
        assert after != null;
        assert !"node-2".equals(after) : "Removed node should not be returned";
        System.out.println("PASS: Removed node no longer serves requests");

        // Test 7: Effect of vnode count on distribution
        System.out.println("\n--- Vnode Count vs Distribution ---");
        for (int vnodes : new int[]{1, 10, 50, 150, 500}) {
            ring = new ConsistentHashRing<>(vnodes);
            ring.addNode("X");
            ring.addNode("Y");
            ring.addNode("Z");
            distribution = new HashMap<>();
            for (int i = 0; i < 10000; i++) {
                distribution.merge(ring.getNode("k:" + i), 1, Integer::sum);
            }
            double stddev = calculateStdDev(distribution.values());
            System.out.printf("  vnodes=%3d -> stddev=%.1f (lower=more uniform)\n", vnodes, stddev);
        }

        System.out.println("\nAll tests passed!");
    }

    static double calculateStdDev(Collection<Integer> values) {
        double mean = values.stream().mapToInt(Integer::intValue).average().orElse(0);
        double variance = values.stream()
            .mapToDouble(v -> Math.pow(v - mean, 2))
            .average().orElse(0);
        return Math.sqrt(variance);
    }
}
