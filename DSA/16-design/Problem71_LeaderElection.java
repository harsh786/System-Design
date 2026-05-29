import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Problem 71: Leader Election (Bully Algorithm)
 * 
 * PRODUCTION MAPPING: ZooKeeper leader election, etcd leader, Raft (leader-based),
 *                     Kafka controller election, Elasticsearch master election
 * 
 * Bully Algorithm:
 * - Each node has a unique ID (higher = higher priority)
 * - When a node detects leader failure, it starts an election
 * - Node sends ELECTION to all higher-ID nodes
 * - If no response: it becomes leader (announces COORDINATOR)
 * - If response: wait for higher node to become leader
 * 
 * Properties:
 * - Highest alive node always becomes leader
 * - O(n²) messages in worst case
 * - Assumes reliable failure detection (unrealistic in practice)
 * 
 * Trade-offs vs other algorithms:
 * - Bully: simple but chatty, highest ID wins (not most capable)
 * - Raft: log-based, leader has most up-to-date log
 * - ZooKeeper: ephemeral sequential nodes, smallest seq# = leader
 * 
 * Staff insight: In production, use lease-based leadership (TTL).
 * Leader must renew lease. If it fails, others can claim.
 */
public class Problem71_LeaderElection {

    enum MessageType { ELECTION, OK, COORDINATOR, HEARTBEAT }

    static class ElectionMessage {
        final MessageType type;
        final int senderId;
        ElectionMessage(MessageType type, int senderId) { this.type = type; this.senderId = senderId; }
    }

    static class Node {
        final int id;
        volatile boolean alive = true;
        volatile int leaderId = -1;
        volatile boolean electionInProgress = false;
        final BlockingQueue<ElectionMessage> inbox = new LinkedBlockingQueue<>();
        Cluster cluster;
        final List<String> log = new CopyOnWriteArrayList<>();

        Node(int id) { this.id = id; }

        void startElection() {
            if (electionInProgress) return;
            electionInProgress = true;
            log.add("Starting election");

            boolean higherNodeResponded = false;
            
            // Send ELECTION to all higher-ID nodes
            for (Node other : cluster.getNodes()) {
                if (other.id > this.id && other.alive) {
                    other.inbox.offer(new ElectionMessage(MessageType.ELECTION, this.id));
                }
            }

            // Wait for OK responses
            try {
                long deadline = System.currentTimeMillis() + 200;
                while (System.currentTimeMillis() < deadline) {
                    ElectionMessage msg = inbox.poll(50, TimeUnit.MILLISECONDS);
                    if (msg != null && msg.type == MessageType.OK) {
                        higherNodeResponded = true;
                        log.add("Received OK from " + msg.senderId + ", deferring");
                        break;
                    }
                    if (msg != null && msg.type == MessageType.COORDINATOR) {
                        leaderId = msg.senderId;
                        electionInProgress = false;
                        log.add("Leader announced: " + msg.senderId);
                        return;
                    }
                }
            } catch (InterruptedException e) { return; }

            if (!higherNodeResponded) {
                // I am the leader!
                becomeLeader();
            }
            electionInProgress = false;
        }

        void becomeLeader() {
            leaderId = this.id;
            log.add("I am the new leader!");
            // Announce to all nodes
            for (Node other : cluster.getNodes()) {
                if (other.id != this.id && other.alive) {
                    other.inbox.offer(new ElectionMessage(MessageType.COORDINATOR, this.id));
                }
            }
        }

        void processMessages() {
            ElectionMessage msg;
            while ((msg = inbox.poll()) != null) {
                switch (msg.type) {
                    case ELECTION:
                        // Higher ID node responds OK and starts own election
                        Node sender = cluster.getNode(msg.senderId);
                        if (sender != null) {
                            sender.inbox.offer(new ElectionMessage(MessageType.OK, this.id));
                        }
                        log.add("Received ELECTION from " + msg.senderId + ", sending OK");
                        startElection(); // I'm higher, I'll take over
                        break;
                    case COORDINATOR:
                        leaderId = msg.senderId;
                        electionInProgress = false;
                        log.add("Accepted leader: " + msg.senderId);
                        break;
                    case HEARTBEAT:
                        // Leader is alive
                        break;
                }
            }
        }

        void crash() {
            alive = false;
            log.add("CRASHED");
        }

        void recover() {
            alive = true;
            leaderId = -1;
            log.add("RECOVERED - starting election");
            startElection();
        }
    }

    static class Cluster {
        private final List<Node> nodes = new ArrayList<>();

        void addNode(Node node) {
            node.cluster = this;
            nodes.add(node);
        }

        List<Node> getNodes() { return nodes; }
        
        Node getNode(int id) {
            for (Node n : nodes) if (n.id == id) return n;
            return null;
        }

        Node getLeader() {
            for (Node n : nodes) {
                if (n.alive && n.leaderId == n.id) return n;
            }
            return null;
        }

        void processAllMessages() {
            for (Node n : nodes) {
                if (n.alive) n.processMessages();
            }
        }
    }

    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Leader Election (Bully Algorithm) ===\n");

        // Test 1: Initial election - highest ID wins
        Cluster cluster = new Cluster();
        Node n1 = new Node(1); cluster.addNode(n1);
        Node n2 = new Node(2); cluster.addNode(n2);
        Node n3 = new Node(3); cluster.addNode(n3);
        Node n4 = new Node(4); cluster.addNode(n4);
        Node n5 = new Node(5); cluster.addNode(n5);

        n1.startElection();
        Thread.sleep(300);
        cluster.processAllMessages();
        Thread.sleep(300);
        cluster.processAllMessages();

        // Node 5 should be leader (highest ID)
        assert n5.leaderId == 5 : "Node 5 should be leader, got: " + n5.leaderId;
        System.out.println("PASS: Highest ID (5) becomes leader");

        // Test 2: Leader crash triggers re-election
        n5.crash();
        // Node 1 detects and starts election
        n1.startElection();
        Thread.sleep(300);
        cluster.processAllMessages();
        Thread.sleep(300);
        cluster.processAllMessages();

        // Node 4 should now be leader
        assert n4.leaderId == 4 : "Node 4 should be leader after 5 crashes";
        System.out.println("PASS: After leader crash, node 4 becomes leader");

        // Test 3: Recovered node with higher ID takes over
        n5.recover();
        Thread.sleep(300);
        cluster.processAllMessages();
        Thread.sleep(100);

        assert n5.leaderId == 5 : "Recovered node 5 should reclaim leadership";
        System.out.println("PASS: Recovered highest node reclaims leadership");

        // Test 4: Multiple crashes - third highest takes over
        cluster = new Cluster();
        n1 = new Node(1); cluster.addNode(n1);
        n2 = new Node(2); cluster.addNode(n2);
        n3 = new Node(3); cluster.addNode(n3);

        n3.startElection();
        Thread.sleep(200);
        cluster.processAllMessages();
        assert n3.leaderId == 3;

        n3.crash();
        n2.startElection();
        Thread.sleep(200);
        cluster.processAllMessages();
        assert n2.leaderId == 2;

        n2.crash();
        n1.startElection();
        Thread.sleep(200);
        assert n1.leaderId == 1;
        System.out.println("PASS: Cascade failure - each next highest takes over");

        // Test 5: Only one node alive
        cluster = new Cluster();
        Node solo = new Node(42); cluster.addNode(solo);
        solo.startElection();
        Thread.sleep(250);
        assert solo.leaderId == 42;
        System.out.println("PASS: Single node elects itself");

        // Print election log
        System.out.println("\nNode 1 log: " + n1.log);

        System.out.println("\nAll tests passed!");
    }
}
