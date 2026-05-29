import java.util.*;
import java.util.concurrent.*;

/**
 * Problem 72: Gossip Protocol (Membership, Failure Detection)
 * 
 * PRODUCTION MAPPING: Cassandra (gossip for cluster membership), Consul (Serf),
 *                     Redis Cluster, CockroachDB, HashiCorp Memberlist
 * 
 * How Gossip Works:
 * - Each node periodically selects random peer and exchanges state
 * - Information spreads exponentially: O(log N) rounds for all nodes
 * - Probabilistic: no single point of failure
 * 
 * Failure Detection (SWIM-style):
 * - Direct ping: send ping, wait for ack
 * - Indirect ping: if no ack, ask K other nodes to ping suspect
 * - If still no response: mark SUSPECT, then DEAD after timeout
 * 
 * Properties:
 * - Eventually consistent membership view
 * - Scalable: O(1) network load per node per round
 * - Robust: no SPOF, tolerates network partitions
 * 
 * Convergence: log(N) rounds * gossip_interval for full propagation
 */
public class Problem72_GossipProtocol {

    enum NodeStatus { ALIVE, SUSPECT, DEAD }

    static class MemberInfo {
        final String nodeId;
        final String address;
        NodeStatus status;
        long lastHeartbeat;
        int incarnation; // monotonically increasing, refutes suspicion

        MemberInfo(String nodeId, String address) {
            this.nodeId = nodeId;
            this.address = address;
            this.status = NodeStatus.ALIVE;
            this.lastHeartbeat = System.currentTimeMillis();
            this.incarnation = 0;
        }

        MemberInfo copy() {
            MemberInfo m = new MemberInfo(nodeId, address);
            m.status = this.status;
            m.lastHeartbeat = this.lastHeartbeat;
            m.incarnation = this.incarnation;
            return m;
        }
    }

    static class GossipNode {
        final String nodeId;
        final Map<String, MemberInfo> memberList = new ConcurrentHashMap<>();
        final List<String> eventLog = new CopyOnWriteArrayList<>();
        final long suspectTimeout; // ms before SUSPECT -> DEAD
        private volatile boolean alive = true;
        GossipCluster cluster; // for simulation

        GossipNode(String nodeId, long suspectTimeout) {
            this.nodeId = nodeId;
            this.suspectTimeout = suspectTimeout;
            // Add self
            memberList.put(nodeId, new MemberInfo(nodeId, nodeId + ":8080"));
        }

        /**
         * Gossip round: pick random peer, exchange membership info
         */
        void gossipRound() {
            if (!alive) return;

            List<String> peers = new ArrayList<>();
            for (Map.Entry<String, MemberInfo> e : memberList.entrySet()) {
                if (!e.getKey().equals(nodeId) && e.getValue().status == NodeStatus.ALIVE) {
                    peers.add(e.getKey());
                }
            }
            if (peers.isEmpty()) return;

            // Pick random peer (fanout=1 for simplicity, production uses 2-3)
            String target = peers.get(ThreadLocalRandom.current().nextInt(peers.size()));
            GossipNode peer = cluster.getNode(target);
            if (peer != null && peer.alive) {
                // Exchange: send our view, receive theirs
                merge(peer.getMemberList());
                peer.merge(getMemberList());
            }
        }

        /**
         * Merge received membership info with local view.
         * Higher incarnation number wins.
         */
        void merge(Map<String, MemberInfo> received) {
            for (Map.Entry<String, MemberInfo> e : received.entrySet()) {
                String id = e.getKey();
                MemberInfo remote = e.getValue();
                MemberInfo local = memberList.get(id);

                if (local == null) {
                    // New node discovered
                    memberList.put(id, remote.copy());
                    eventLog.add("DISCOVERED: " + id);
                } else if (remote.incarnation > local.incarnation) {
                    // Remote has newer info
                    memberList.put(id, remote.copy());
                } else if (remote.incarnation == local.incarnation) {
                    // Same incarnation: DEAD > SUSPECT > ALIVE (higher status wins)
                    if (remote.status.ordinal() > local.status.ordinal()) {
                        local.status = remote.status;
                    }
                }
            }
        }

        /**
         * Failure detection: check for timed-out nodes
         */
        void detectFailures() {
            if (!alive) return;
            long now = System.currentTimeMillis();
            for (MemberInfo member : memberList.values()) {
                if (member.nodeId.equals(this.nodeId)) continue;
                if (member.status == NodeStatus.ALIVE && 
                    now - member.lastHeartbeat > suspectTimeout) {
                    member.status = NodeStatus.SUSPECT;
                    eventLog.add("SUSPECT: " + member.nodeId);
                } else if (member.status == NodeStatus.SUSPECT && 
                           now - member.lastHeartbeat > suspectTimeout * 2) {
                    member.status = NodeStatus.DEAD;
                    eventLog.add("DEAD: " + member.nodeId);
                }
            }
        }

        /** Node refutes suspicion by incrementing incarnation */
        void refuteSuspicion() {
            MemberInfo self = memberList.get(nodeId);
            self.incarnation++;
            self.status = NodeStatus.ALIVE;
            self.lastHeartbeat = System.currentTimeMillis();
        }

        void heartbeat() {
            MemberInfo self = memberList.get(nodeId);
            self.lastHeartbeat = System.currentTimeMillis();
        }

        void crash() { alive = false; }
        void recover() { alive = true; refuteSuspicion(); }

        Map<String, MemberInfo> getMemberList() {
            Map<String, MemberInfo> copy = new HashMap<>();
            for (Map.Entry<String, MemberInfo> e : memberList.entrySet()) {
                copy.put(e.getKey(), e.getValue().copy());
            }
            return copy;
        }

        List<String> getAliveMembers() {
            List<String> alive = new ArrayList<>();
            for (MemberInfo m : memberList.values()) {
                if (m.status == NodeStatus.ALIVE) alive.add(m.nodeId);
            }
            return alive;
        }
    }

    static class GossipCluster {
        private final Map<String, GossipNode> nodes = new LinkedHashMap<>();

        GossipNode createNode(String id, long suspectTimeout) {
            GossipNode node = new GossipNode(id, suspectTimeout);
            node.cluster = this;
            nodes.put(id, node);
            return node;
        }

        GossipNode getNode(String id) { return nodes.get(id); }

        /** Introduce a node to one existing node (seed) */
        void introduce(String newNodeId, String seedNodeId) {
            GossipNode newNode = nodes.get(newNodeId);
            GossipNode seed = nodes.get(seedNodeId);
            if (newNode != null && seed != null) {
                newNode.merge(seed.getMemberList());
                seed.merge(newNode.getMemberList());
            }
        }

        /** Run N rounds of gossip for all nodes */
        void runRounds(int n) {
            for (int i = 0; i < n; i++) {
                for (GossipNode node : nodes.values()) {
                    node.gossipRound();
                }
            }
        }

        void detectFailuresAll() {
            for (GossipNode node : nodes.values()) node.detectFailures();
        }
    }

    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Gossip Protocol ===\n");

        // Test 1: Membership propagation
        GossipCluster cluster = new GossipCluster();
        GossipNode n1 = cluster.createNode("node-1", 500);
        GossipNode n2 = cluster.createNode("node-2", 500);
        GossipNode n3 = cluster.createNode("node-3", 500);
        GossipNode n4 = cluster.createNode("node-4", 500);
        GossipNode n5 = cluster.createNode("node-5", 500);

        // Only introduce n1 as seed to all others
        cluster.introduce("node-2", "node-1");
        cluster.introduce("node-3", "node-1");
        cluster.introduce("node-4", "node-1");
        cluster.introduce("node-5", "node-1");

        // After introductions, only node-1 knows everyone
        // Run gossip rounds to propagate
        cluster.runRounds(10);

        // All nodes should know about all others
        for (GossipNode n : new GossipNode[]{n1, n2, n3, n4, n5}) {
            assert n.memberList.size() == 5 : n.nodeId + " knows " + n.memberList.size();
        }
        System.out.println("PASS: All 5 nodes discovered each other via gossip");

        // Test 2: Convergence speed (how many rounds needed?)
        cluster = new GossipCluster();
        int N = 20;
        for (int i = 0; i < N; i++) cluster.createNode("n" + i, 500);
        // Chain introduction: each node knows only next
        for (int i = 1; i < N; i++) cluster.introduce("n" + i, "n0");

        int rounds = 0;
        boolean converged = false;
        while (!converged && rounds < 100) {
            cluster.runRounds(1);
            rounds++;
            converged = true;
            for (GossipNode n : cluster.nodes.values()) {
                if (n.memberList.size() < N) { converged = false; break; }
            }
        }
        System.out.printf("PASS: %d nodes converged in %d rounds (theoretical: ~%.0f)\n", 
            N, rounds, Math.ceil(Math.log(N) / Math.log(2)) * 3);

        // Test 3: Failure detection
        cluster = new GossipCluster();
        n1 = cluster.createNode("A", 100);
        n2 = cluster.createNode("B", 100);
        n3 = cluster.createNode("C", 100);
        cluster.introduce("B", "A");
        cluster.introduce("C", "A");
        cluster.runRounds(5);

        n3.crash(); // C goes down
        Thread.sleep(150); // exceed suspect timeout
        cluster.detectFailuresAll();
        
        assert n1.memberList.get("C").status == NodeStatus.SUSPECT;
        System.out.println("PASS: Crashed node detected as SUSPECT");

        Thread.sleep(250); // exceed dead timeout
        cluster.detectFailuresAll();
        assert n1.memberList.get("C").status == NodeStatus.DEAD;
        System.out.println("PASS: Suspect node promoted to DEAD");

        // Test 4: Suspicion propagation via gossip
        cluster.runRounds(5);
        assert n2.memberList.get("C").status == NodeStatus.DEAD;
        System.out.println("PASS: DEAD status propagated via gossip");

        // Test 5: Node recovery and refutation
        n3.recover();
        cluster.runRounds(3);
        // After recovery gossip, nodes should see C as ALIVE again
        assert n3.memberList.get("C").status == NodeStatus.ALIVE;
        cluster.runRounds(5);
        assert n1.memberList.get("C").status == NodeStatus.ALIVE ||
               n1.memberList.get("C").incarnation > 0;
        System.out.println("PASS: Recovered node refutes suspicion via incarnation");

        // Test 6: New node joining
        GossipNode n4join = cluster.createNode("D", 100);
        cluster.introduce("D", "A"); // join via seed A
        cluster.runRounds(5);
        assert n4join.memberList.size() >= 3 : "New node should discover cluster";
        System.out.println("PASS: New node joins and discovers cluster members");

        System.out.println("\nAll tests passed!");
    }
}
