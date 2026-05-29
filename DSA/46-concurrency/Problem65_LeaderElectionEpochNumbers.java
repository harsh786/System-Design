import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.*;

/**
 * Problem 65: Leader Election with Epoch Numbers
 * 
 * REAL-WORLD USAGE:
 * - Raft consensus (term numbers)
 * - ZooKeeper ZAB protocol (epoch/zxid)
 * - Kafka controller election (controller epoch)
 * - etcd leader election (lease + revision)
 * - Paxos (ballot numbers / proposal numbers)
 * 
 * KEY CONCEPTS:
 * - Epoch (term): monotonically increasing number identifying a leadership period
 * - Only ONE leader per epoch (safety property)
 * - Old leaders with stale epochs are rejected by followers
 * - Leader sends heartbeats; if missed, followers trigger new election
 * - Epoch prevents "zombie leaders" (leaders that think they're still leader after partition)
 * 
 * WHY EPOCHS MATTER:
 * - Network partition → two nodes think they're leader
 * - Epoch guarantees: the one with HIGHER epoch wins
 * - Any operation tagged with an old epoch is REJECTED
 * - Same concept as fencing tokens but for consensus/replication
 * 
 * MEMORY ORDERING:
 * - Epoch transitions must be linearizable (total order across all nodes)
 * - Voting must be durable before responding (crash safety)
 * - Leader's first act is writing a "new term" entry (establishes authority)
 */
public class Problem65_LeaderElectionEpochNumbers {

    enum NodeState { FOLLOWER, CANDIDATE, LEADER }

    // ==================== RAFT-LIKE NODE ====================
    static class RaftNode implements Runnable {
        private final int nodeId;
        private List<RaftNode> cluster;
        private volatile NodeState state = NodeState.FOLLOWER;
        private final AtomicLong currentEpoch = new AtomicLong(0);
        private volatile int votedFor = -1; // Who we voted for in current epoch
        private volatile int leaderId = -1;
        private volatile long lastHeartbeat = System.currentTimeMillis();
        private final int electionTimeoutMs;
        private volatile boolean running = true;

        // Stats
        final AtomicInteger electionsWon = new AtomicInteger(0);
        final AtomicInteger heartbeatsSent = new AtomicInteger(0);
        final AtomicInteger staleRequestsRejected = new AtomicInteger(0);

        RaftNode(int nodeId, int electionTimeoutMs) {
            this.nodeId = nodeId;
            this.cluster = new ArrayList<>();
            this.electionTimeoutMs = electionTimeoutMs + new Random().nextInt(150); // Randomized timeout
        }

        void setCluster(List<RaftNode> cluster) { this.cluster = cluster; }

        @Override
        public void run() {
            while (running) {
                switch (state) {
                    case FOLLOWER:
                        runFollower();
                        break;
                    case CANDIDATE:
                        runCandidate();
                        break;
                    case LEADER:
                        runLeader();
                        break;
                }
            }
        }

        private void runFollower() {
            if (System.currentTimeMillis() - lastHeartbeat > electionTimeoutMs) {
                // Heartbeat timeout - start election
                state = NodeState.CANDIDATE;
            } else {
                sleep(10);
            }
        }

        private void runCandidate() {
            // Increment epoch and vote for self
            long newEpoch = currentEpoch.incrementAndGet();
            votedFor = nodeId;
            int votesReceived = 1; // Self-vote

            // Request votes from all other nodes
            for (RaftNode peer : cluster) {
                if (peer.nodeId == nodeId) continue;
                if (peer.requestVote(nodeId, newEpoch)) {
                    votesReceived++;
                }
            }

            // Check if won majority
            if (votesReceived > cluster.size() / 2) {
                state = NodeState.LEADER;
                leaderId = nodeId;
                electionsWon.incrementAndGet();
                // Immediately send heartbeats to establish authority
                sendHeartbeats();
            } else {
                // Lost election - back to follower
                state = NodeState.FOLLOWER;
                sleep(new Random().nextInt(50)); // Random backoff
            }
        }

        private void runLeader() {
            sendHeartbeats();
            sleep(30); // Heartbeat interval
        }

        /**
         * Handle vote request. Grant vote if:
         * 1. Candidate's epoch > our current epoch
         * 2. We haven't voted for someone else in this epoch
         */
        public synchronized boolean requestVote(int candidateId, long candidateEpoch) {
            if (candidateEpoch > currentEpoch.get()) {
                // Higher epoch - step down if leader, grant vote
                currentEpoch.set(candidateEpoch);
                state = NodeState.FOLLOWER;
                votedFor = candidateId;
                return true;
            }
            if (candidateEpoch == currentEpoch.get() && (votedFor == -1 || votedFor == candidateId)) {
                votedFor = candidateId;
                return true;
            }
            return false; // Reject: stale epoch or already voted
        }

        /**
         * Handle heartbeat (AppendEntries in Raft).
         * Reject if leader's epoch is stale.
         */
        public synchronized boolean receiveHeartbeat(int leaderIdParam, long leaderEpoch) {
            if (leaderEpoch < currentEpoch.get()) {
                // STALE leader! Reject.
                staleRequestsRejected.incrementAndGet();
                return false;
            }
            if (leaderEpoch > currentEpoch.get()) {
                currentEpoch.set(leaderEpoch);
            }
            state = NodeState.FOLLOWER;
            leaderId = leaderIdParam;
            lastHeartbeat = System.currentTimeMillis();
            votedFor = -1; // Reset vote for next epoch
            return true;
        }

        private void sendHeartbeats() {
            long epoch = currentEpoch.get();
            for (RaftNode peer : cluster) {
                if (peer.nodeId == nodeId) continue;
                if (!peer.receiveHeartbeat(nodeId, epoch)) {
                    // Our epoch is stale - step down!
                    state = NodeState.FOLLOWER;
                    return;
                }
                heartbeatsSent.incrementAndGet();
            }
        }

        public void stop() { running = false; }
        private void sleep(long ms) { try { Thread.sleep(ms); } catch (InterruptedException e) { running = false; } }
        public int getNodeId() { return nodeId; }
        public NodeState getState() { return state; }
        public long getEpoch() { return currentEpoch.get(); }
        public int getLeaderId() { return leaderId; }
    }

    // ==================== SIMULATION ====================
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Leader Election with Epoch Numbers ===\n");

        int clusterSize = 5;
        List<RaftNode> cluster = new ArrayList<>();
        for (int i = 0; i < clusterSize; i++) {
            cluster.add(new RaftNode(i, 200 + i * 30)); // Staggered timeouts
        }
        for (RaftNode node : cluster) {
            node.setCluster(cluster);
        }

        // Start all nodes
        List<Thread> threads = new ArrayList<>();
        for (RaftNode node : cluster) {
            Thread t = new Thread(node, "Node-" + node.getNodeId());
            t.setDaemon(true);
            threads.add(t);
            t.start();
        }

        // Let them elect a leader
        Thread.sleep(500);
        System.out.println("--- Initial Election ---");
        printClusterState(cluster);

        // Simulate leader crash
        RaftNode leader = cluster.stream().filter(n -> n.getState() == NodeState.LEADER).findFirst().orElse(null);
        if (leader != null) {
            System.out.println("\n--- Killing leader (Node " + leader.getNodeId() + ") ---");
            leader.stop();
            Thread.sleep(500); // Wait for new election
            System.out.println("--- After re-election ---");
            printClusterState(cluster);
        }

        // Let it run more
        Thread.sleep(1000);
        System.out.println("\n--- Final State ---");
        printClusterState(cluster);

        // Stop all
        for (RaftNode node : cluster) node.stop();
        for (Thread t : threads) t.join(500);

        System.out.println("\n--- Statistics ---");
        for (RaftNode node : cluster) {
            System.out.printf("Node %d: elections_won=%d, heartbeats_sent=%d, stale_rejected=%d, epoch=%d%n",
                    node.getNodeId(), node.electionsWon.get(), node.heartbeatsSent.get(),
                    node.staleRequestsRejected.get(), node.getEpoch());
        }
        System.out.println("\nKey insight: Epoch numbers prevent split-brain.");
        System.out.println("A zombie leader with epoch 5 is rejected by nodes at epoch 6.");
        System.out.println("This is how Raft, ZAB, and Kafka controller ensure single-leader safety.");
    }

    private static void printClusterState(List<RaftNode> cluster) {
        for (RaftNode node : cluster) {
            System.out.printf("  Node %d: state=%s, epoch=%d, leader=%d%n",
                    node.getNodeId(), node.getState(), node.getEpoch(), node.getLeaderId());
        }
    }
}
