import java.util.*;

/**
 * Problem 7: Eulerian Circuit in Undirected Graph
 * 
 * Find a circuit that traverses every edge exactly once and returns to start.
 * 
 * Conditions: All vertices have even degree AND graph is connected.
 * 
 * Fleury's Algorithm (conceptual, O(E^2)):
 * - Don't cross a bridge unless no alternative
 * 
 * Hierholzer's Algorithm (efficient, O(E)):
 * - More efficient, implemented here
 * 
 * Applications: Circuit board testing, snow plowing routes, DNA fragment assembly
 */
public class Problem07_EulerianCircuitUndirected {

    public static List<Integer> findEulerianCircuit(int n, List<int[]> edges) {
        int[] degree = new int[n];
        List<List<int[]>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        boolean[] usedEdge = new boolean[edges.size()];
        
        for (int i = 0; i < edges.size(); i++) {
            int u = edges.get(i)[0], v = edges.get(i)[1];
            adj.get(u).add(new int[]{v, i});
            adj.get(v).add(new int[]{u, i});
            degree[u]++;
            degree[v]++;
        }
        
        // Check conditions
        for (int i = 0; i < n; i++) {
            if (degree[i] % 2 != 0) return null; // Odd degree vertex
        }
        
        int[] adjPtr = new int[n];
        LinkedList<Integer> circuit = new LinkedList<>();
        Deque<Integer> stack = new ArrayDeque<>();
        stack.push(0);
        
        while (!stack.isEmpty()) {
            int v = stack.peek();
            boolean found = false;
            while (adjPtr[v] < adj.get(v).size()) {
                int[] e = adj.get(v).get(adjPtr[v]);
                adjPtr[v]++;
                if (!usedEdge[e[1]]) {
                    usedEdge[e[1]] = true;
                    stack.push(e[0]);
                    found = true;
                    break;
                }
            }
            if (!found) circuit.addFirst(stack.pop());
        }
        
        return circuit.size() == edges.size() + 1 ? circuit : null;
    }

    public static void main(String[] args) {
        // Complete graph K4 (every vertex degree 3 - odd, no circuit)
        System.out.println("K4 (all degree 3):");
        List<int[]> k4 = Arrays.asList(
            new int[]{0,1}, new int[]{0,2}, new int[]{0,3},
            new int[]{1,2}, new int[]{1,3}, new int[]{2,3});
        List<Integer> result = findEulerianCircuit(4, k4);
        System.out.println("Circuit: " + (result != null ? result : "None (odd degrees)"));
        
        // Graph with all even degrees
        System.out.println("\nSquare with diagonals (degrees: 4,3,4,3 - mixed, add edges):");
        // Make all degrees even: square + cross
        List<int[]> evenGraph = Arrays.asList(
            new int[]{0,1}, new int[]{1,2}, new int[]{2,3}, new int[]{3,0},
            new int[]{0,2}, new int[]{1,3});
        // Degrees: 0->3, 1->3, 2->3, 3->3 (all odd - no circuit)
        // Let's use a proper example: two triangles sharing an edge
        List<int[]> proper = Arrays.asList(
            new int[]{0,1}, new int[]{1,2}, new int[]{2,0},
            new int[]{0,3}, new int[]{3,2}, new int[]{2,0}); // extra 2-0 edge
        // degrees: 0=4, 1=2, 2=4, 3=2 (all even!)
        result = findEulerianCircuit(4, proper);
        System.out.println("Two-triangle graph circuit: " + result);
    }
}
