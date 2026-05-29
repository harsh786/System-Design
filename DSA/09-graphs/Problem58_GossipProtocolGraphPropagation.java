import java.util.*;

/**
 * Problem 58: Gossip Protocol Graph Propagation
 * 
 * Production Relevance:
 * - Epidemic protocols for cluster membership, failure detection (Cassandra, Consul, SWIM)
 * - Eventually consistent state propagation without central coordinator
 * - Scalable: O(log N) rounds to reach all nodes with high probability
 * - Used for membership lists, config propagation, load information sharing
 * 
 * Architect Considerations:
 * - Fanout (number of peers to gossip to) vs convergence time vs bandwidth
 * - Pull vs push vs push-pull gossip variants
 * - Version vectors to detect stale vs fresh information
 * - Failure detection integrated with gossip (piggybacking)
 */
public class Problem58_GossipProtocolGraphPropagation {

    static class GossipState {
        Map<String, Long> versions = new HashMap<>(); // key -> version timestamp
        Map<String, String> data = new HashMap<>();

        void update(String key, String value, long version) {
            if (version > versions.getOrDefault(key, 0L)) {
                versions.put(key, version);
                data.put(key, value);
            }
        }

        // Merge incoming gossip (take newer versions)
        int merge(GossipState incoming) {
            int updates = 0;
            for (Map.Entry<String, Long> entry : incoming.versions.entrySet()) {
                if (entry.getValue() > versions.getOrDefault(entry.getKey(), 0L)) {
                    versions.put(entry.getKey(), entry.getValue());
                    data.put(entry.getKey(), incoming.data.get(entry.getKey()));
                    updates++;
                }
            }
            return updates;
        }
    }

    static class GossipNode {
        String id;
        GossipState state = new GossipState();
        List<String> peers = new ArrayList<>();

        GossipNode(String id) { this.id = id; }
    }

    static class GossipCluster {
        Map<String, GossipNode> nodes = new LinkedHashMap<>();
        int fanout;
        Random random = new Random(42);
        int totalMessages = 0;

        GossipCluster(int fanout) { this.fanout = fanout; }

        void addNode(String id) {
            GossipNode node = new GossipNode(id);
            // Connect to all existing nodes (full mesh awareness)
            for (String existing : nodes.keySet()) {
                node.peers.add(existing);
                nodes.get(existing).peers.add(id);
            }
            nodes.put(id, node);
        }

        // Originate an update at a specific node
        void originateUpdate(String nodeId, String key, String value, long version) {
            nodes.get(nodeId).state.update(key, value, version);
        }

        // Run one round of gossip (each node pushes to 'fanout' random peers)
        int gossipRound() {
            int totalUpdates = 0;
            for (GossipNode node : nodes.values()) {
                List<String> targets = selectTargets(node);
                for (String target : targets) {
                    GossipNode peer = nodes.get(target);
                    totalUpdates += peer.state.merge(node.state);
                    totalMessages++;
                }
            }
            return totalUpdates;
        }

        private List<String> selectTargets(GossipNode node) {
            List<String> peers = new ArrayList<>(node.peers);
            Collections.shuffle(peers, random);
            return peers.subList(0, Math.min(fanout, peers.size()));
        }

        // Check convergence: all nodes have same state
        boolean isConverged() {
            GossipState reference = nodes.values().iterator().next().state;
            for (GossipNode node : nodes.values()) {
                if (!node.state.versions.equals(reference.versions)) return false;
            }
            return true;
        }

        int getConvergedNodeCount(String key) {
            long maxVersion = nodes.values().stream()
                    .mapToLong(n -> n.state.versions.getOrDefault(key, 0L)).max().orElse(0);
            return (int) nodes.values().stream()
                    .filter(n -> n.state.versions.getOrDefault(key, 0L) == maxVersion).count();
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Gossip Protocol Graph Propagation ===\n");

        GossipCluster cluster = new GossipCluster(3); // fanout = 3
        for (int i = 1; i <= 20; i++) cluster.addNode("node" + i);

        // Node1 gets an update
        cluster.originateUpdate("node1", "config.version", "2.0.0", System.currentTimeMillis());
        System.out.printf("Cluster: %d nodes, fanout: %d%n", cluster.nodes.size(), cluster.fanout);
        System.out.println("Update originated at node1\n");

        // Run gossip rounds until convergence
        int round = 0;
        while (!cluster.isConverged()) {
            int updates = cluster.gossipRound();
            round++;
            int converged = cluster.getConvergedNodeCount("config.version");
            System.out.printf("Round %d: %d updates, %d/%d nodes converged%n",
                    round, updates, converged, cluster.nodes.size());
        }

        System.out.printf("%nConverged in %d rounds, %d total messages%n", round, cluster.totalMessages);
        System.out.printf("Theoretical minimum: O(log_%d(%d)) = %.1f rounds%n",
                cluster.fanout, cluster.nodes.size(),
                Math.log(cluster.nodes.size()) / Math.log(cluster.fanout));
    }
}
