import java.util.*;

/**
 * Problem 57: Network Partition Detection
 * 
 * Production Relevance:
 * - Split-brain in distributed systems: cluster divides into isolated groups
 * - Must detect partitions to invoke quorum rules, leader election, fencing
 * - Used in ZooKeeper, etcd, Consul for cluster health monitoring
 * - CAP theorem: during partition, choose consistency or availability
 * 
 * Architect Considerations:
 * - Heartbeat-based detection with phi-accrual failure detector
 * - Graph connectivity: find connected components after edge failures
 * - Quorum: which partition gets to continue serving (majority wins)
 */
public class Problem57_NetworkPartitionDetection {

    static class ClusterNode {
        String id;
        String datacenter;
        boolean isLeader;

        ClusterNode(String id, String dc) { this.id = id; this.datacenter = dc; }
    }

    static class NetworkTopology {
        Map<String, ClusterNode> nodes = new LinkedHashMap<>();
        Map<String, Set<String>> connections = new HashMap<>(); // bidirectional

        void addNode(String id, String dc) {
            nodes.put(id, new ClusterNode(id, dc));
            connections.put(id, new HashSet<>());
        }

        void addLink(String a, String b) {
            connections.get(a).add(b);
            connections.get(b).add(a);
        }

        void removeLink(String a, String b) {
            connections.get(a).remove(b);
            connections.get(b).remove(a);
        }

        // Find connected components (partitions)
        List<Set<String>> detectPartitions() {
            List<Set<String>> partitions = new ArrayList<>();
            Set<String> visited = new HashSet<>();

            for (String node : nodes.keySet()) {
                if (!visited.contains(node)) {
                    Set<String> component = new HashSet<>();
                    Queue<String> queue = new LinkedList<>();
                    queue.offer(node);
                    while (!queue.isEmpty()) {
                        String curr = queue.poll();
                        if (!visited.add(curr)) continue;
                        component.add(curr);
                        for (String neighbor : connections.get(curr)) {
                            if (!visited.contains(neighbor)) queue.offer(neighbor);
                        }
                    }
                    partitions.add(component);
                }
            }
            return partitions;
        }

        // Determine which partition has quorum
        Set<String> getQuorumPartition() {
            List<Set<String>> partitions = detectPartitions();
            int majority = nodes.size() / 2 + 1;
            for (Set<String> p : partitions) {
                if (p.size() >= majority) return p;
            }
            return Collections.emptySet(); // No partition has quorum!
        }

        // Find minimum links whose failure would partition the network (bridges)
        List<String[]> findBridges() {
            List<String[]> bridges = new ArrayList<>();
            Map<String, Integer> disc = new HashMap<>(), low = new HashMap<>();
            Set<String> visited = new HashSet<>();
            int[] timer = {0};

            for (String node : nodes.keySet()) {
                if (!visited.contains(node)) {
                    dfsBridge(node, null, visited, disc, low, bridges, timer);
                }
            }
            return bridges;
        }

        private void dfsBridge(String u, String parent, Set<String> visited,
                               Map<String, Integer> disc, Map<String, Integer> low,
                               List<String[]> bridges, int[] timer) {
            visited.add(u);
            disc.put(u, timer[0]);
            low.put(u, timer[0]);
            timer[0]++;

            for (String v : connections.get(u)) {
                if (!visited.contains(v)) {
                    dfsBridge(v, u, visited, disc, low, bridges, timer);
                    low.put(u, Math.min(low.get(u), low.get(v)));
                    if (low.get(v) > disc.get(u)) bridges.add(new String[]{u, v});
                } else if (!v.equals(parent)) {
                    low.put(u, Math.min(low.get(u), disc.get(v)));
                }
            }
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Network Partition Detection ===\n");

        NetworkTopology topo = new NetworkTopology();
        // 5-node cluster across 2 DCs
        topo.addNode("node1", "dc1"); topo.addNode("node2", "dc1"); topo.addNode("node3", "dc1");
        topo.addNode("node4", "dc2"); topo.addNode("node5", "dc2");

        // Full mesh within DC, cross-DC link
        topo.addLink("node1", "node2"); topo.addLink("node2", "node3"); topo.addLink("node1", "node3");
        topo.addLink("node4", "node5");
        topo.addLink("node3", "node4"); // Cross-DC link

        System.out.println("Before partition:");
        System.out.println("  Partitions: " + topo.detectPartitions());
        System.out.println("  Bridges (single points of failure): ");
        topo.findBridges().forEach(b -> System.out.println("    " + b[0] + " <-> " + b[1]));

        // Simulate network partition (cross-DC link fails)
        topo.removeLink("node3", "node4");
        System.out.println("\nAfter cross-DC link failure:");
        List<Set<String>> partitions = topo.detectPartitions();
        System.out.println("  Partitions: " + partitions);
        System.out.println("  Quorum partition: " + topo.getQuorumPartition());
        System.out.println("  Minority partition (must fence itself): " +
                partitions.stream().filter(p -> p.size() < 3).findFirst().orElse(Set.of()));
    }
}
