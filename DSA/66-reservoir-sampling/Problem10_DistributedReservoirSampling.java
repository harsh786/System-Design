import java.util.*;

/**
 * Problem 10: Distributed Reservoir Sampling
 * 
 * When data is distributed across multiple nodes/partitions, we need to
 * combine local reservoir samples into a global sample.
 * 
 * Algorithm:
 * 1. Each node maintains a local reservoir of size k from its stream
 * 2. To merge: combine all local reservoirs (total = numNodes * k items)
 * 3. Perform weighted reservoir sampling where weight = localStreamSize
 * 
 * Correct approach: Each node tracks (reservoir, streamCount).
 * Global sample: from merged pool, pick k items with probability proportional
 * to the node's stream size contribution.
 */
public class Problem10_DistributedReservoirSampling {

    static class NodeReservoir {
        int[] reservoir;
        int streamCount;
        int nodeId;

        NodeReservoir(int nodeId, int reservoirSize) {
            this.nodeId = nodeId;
            this.reservoir = new int[reservoirSize];
            this.streamCount = 0;
        }

        void processStream(int[] data, Random rand) {
            for (int val : data) {
                if (streamCount < reservoir.length) {
                    reservoir[streamCount] = val;
                } else {
                    int j = rand.nextInt(streamCount + 1);
                    if (j < reservoir.length) reservoir[j] = val;
                }
                streamCount++;
            }
        }
    }

    /**
     * Merge local reservoirs into a global sample of size k.
     * Each element from node i has probability k_local / n_i of being in the local reservoir.
     * For the global sample, we want probability k_global / N where N = sum of all n_i.
     */
    public static int[] mergeReservoirs(List<NodeReservoir> nodes, int globalK, Random rand) {
        int totalStream = 0;
        for (NodeReservoir node : nodes) totalStream += node.streamCount;
        
        // Collect all local samples with their source weights
        List<int[]> candidates = new ArrayList<>(); // [value, nodeStreamCount]
        for (NodeReservoir node : nodes) {
            int localSize = Math.min(node.streamCount, node.reservoir.length);
            for (int i = 0; i < localSize; i++) {
                candidates.add(new int[]{node.reservoir[i], node.streamCount});
            }
        }
        
        // Weighted reservoir sampling on merged candidates
        // Weight of each candidate from node with count n_i: n_i / localReservoirSize
        int[] globalReservoir = new int[globalK];
        double[] globalKeys = new double[globalK];
        Arrays.fill(globalKeys, -1);
        
        for (int[] candidate : candidates) {
            int value = candidate[0];
            double weight = candidate[1]; // Proportional to stream size
            double key = Math.pow(rand.nextDouble(), 1.0 / weight);
            
            // Find min key in reservoir
            int minIdx = 0;
            for (int i = 1; i < globalK; i++) {
                if (globalKeys[i] < globalKeys[minIdx]) minIdx = i;
            }
            
            if (globalKeys[minIdx] < 0 || key > globalKeys[minIdx]) {
                // Check if reservoir is not full yet
                boolean placed = false;
                for (int i = 0; i < globalK; i++) {
                    if (globalKeys[i] < 0) {
                        globalReservoir[i] = value;
                        globalKeys[i] = key;
                        placed = true;
                        break;
                    }
                }
                if (!placed && key > globalKeys[minIdx]) {
                    globalReservoir[minIdx] = value;
                    globalKeys[minIdx] = key;
                }
            }
        }
        return globalReservoir;
    }

    public static void main(String[] args) {
        Random rand = new Random(42);
        int numNodes = 5;
        int localReservoirSize = 100;
        int globalK = 50;
        
        // Each node processes different-sized streams
        int[] streamSizes = {10000, 25000, 5000, 50000, 15000};
        List<NodeReservoir> nodes = new ArrayList<>();
        
        for (int i = 0; i < numNodes; i++) {
            NodeReservoir node = new NodeReservoir(i, localReservoirSize);
            // Stream values are in range [i*1000, (i+1)*1000) to track source
            int[] data = new int[streamSizes[i]];
            for (int j = 0; j < streamSizes[i]; j++) {
                data[j] = i * 1000 + rand.nextInt(1000);
            }
            node.processStream(data, rand);
            nodes.add(node);
        }
        
        // Merge
        int[] globalSample = mergeReservoirs(nodes, globalK, rand);
        
        // Analyze: count items from each node
        int[] nodeCounts = new int[numNodes];
        for (int val : globalSample) {
            nodeCounts[val / 1000]++;
        }
        
        int totalStream = 0;
        for (int s : streamSizes) totalStream += s;
        
        System.out.println("Distributed Reservoir Sampling");
        System.out.printf("Nodes: %d, Global sample: %d%n%n", numNodes, globalK);
        System.out.printf("%-8s %-12s %-12s %-12s%n", "Node", "StreamSize", "Expected%", "Actual%");
        for (int i = 0; i < numNodes; i++) {
            System.out.printf("%-8d %-12d %-12.1f %-12.1f%n", i, streamSizes[i],
                100.0 * streamSizes[i] / totalStream,
                100.0 * nodeCounts[i] / globalK);
        }
        System.out.println("\nLarger streams should contribute proportionally more to global sample.");
    }
}
