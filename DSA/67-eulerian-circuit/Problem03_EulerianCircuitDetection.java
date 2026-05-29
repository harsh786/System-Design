import java.util.*;

/**
 * Problem 3: Eulerian Circuit Detection and Construction
 * 
 * An Eulerian Circuit visits every edge exactly once AND returns to the starting vertex.
 * 
 * Conditions:
 * - Directed: Every vertex has inDegree == outDegree, graph is strongly connected
 * - Undirected: Every vertex has even degree, graph is connected
 * 
 * Construction uses Hierholzer's algorithm:
 * 1. Start at any vertex, follow edges until returning to start (forming a cycle)
 * 2. While there exists a vertex in the circuit with unused edges:
 *    - Start a new traversal from that vertex
 *    - Splice the new cycle into the existing circuit
 */
public class Problem03_EulerianCircuitDetection {

    // Find Eulerian circuit in directed graph
    public static List<Integer> findEulerianCircuit(int n, int[][] edges) {
        int[] inDeg = new int[n], outDeg = new int[n];
        Map<Integer, Deque<Integer>> graph = new HashMap<>();
        
        for (int[] e : edges) {
            outDeg[e[0]]++;
            inDeg[e[1]]++;
            graph.computeIfAbsent(e[0], k -> new ArrayDeque<>()).add(e[1]);
        }
        
        // Check if Eulerian circuit exists
        for (int i = 0; i < n; i++) {
            if (inDeg[i] != outDeg[i]) {
                System.out.println("No Eulerian circuit: vertex " + i + 
                    " has in=" + inDeg[i] + " out=" + outDeg[i]);
                return null;
            }
        }
        
        // Hierholzer's algorithm
        LinkedList<Integer> circuit = new LinkedList<>();
        Deque<Integer> stack = new ArrayDeque<>();
        stack.push(0);
        
        while (!stack.isEmpty()) {
            int v = stack.peek();
            Deque<Integer> neighbors = graph.getOrDefault(v, new ArrayDeque<>());
            if (!neighbors.isEmpty()) {
                stack.push(neighbors.poll());
            } else {
                circuit.addFirst(stack.pop());
            }
        }
        
        // Verify all edges used
        if (circuit.size() != edges.length + 1) {
            System.out.println("Graph is not connected - no Eulerian circuit");
            return null;
        }
        
        return circuit;
    }

    public static void main(String[] args) {
        // Graph with Eulerian circuit: 0->1->2->3->0, 0->2->1->0
        int[][] edges = {{0,1},{1,2},{2,3},{3,0},{0,2},{2,1},{1,0}};
        int n = 4;
        
        System.out.println("Graph edges: " + Arrays.deepToString(edges));
        List<Integer> circuit = findEulerianCircuit(n, edges);
        if (circuit != null) {
            System.out.println("Eulerian Circuit: " + circuit);
            System.out.println("Number of edges traversed: " + (circuit.size() - 1));
        }

        // Graph without Eulerian circuit
        System.out.println("\nGraph without circuit:");
        int[][] edges2 = {{0,1},{1,2},{2,0},{0,3}};
        findEulerianCircuit(4, edges2);
    }
}
