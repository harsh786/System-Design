import java.util.*;

/**
 * Problem 10: Edge-Disjoint Path Decomposition
 * 
 * Decompose a graph into minimum number of edge-disjoint paths/circuits.
 * 
 * Key theorem: A connected graph can be decomposed into:
 * - max(1, oddVertices/2) edge-disjoint paths
 * - Where oddVertices = number of vertices with odd degree
 * - If oddVertices = 0, it can be decomposed into circuits
 * 
 * Algorithm:
 * 1. Find odd-degree vertices
 * 2. Add virtual edges between pairs of odd-degree vertices
 * 3. Find Eulerian circuit in augmented graph
 * 4. Remove virtual edges to split circuit into paths
 */
public class Problem10_EdgeDisjointPathDecomposition {

    public static List<List<Integer>> decomposePaths(int n, int[][] edges) {
        List<List<int[]>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        int[] degree = new int[n];
        boolean[] usedEdge = new boolean[edges.length];
        
        for (int i = 0; i < edges.length; i++) {
            int u = edges[i][0], v = edges[i][1];
            adj.get(u).add(new int[]{v, i});
            adj.get(v).add(new int[]{u, i});
            degree[u]++;
            degree[v]++;
        }
        
        // Find odd-degree vertices
        List<Integer> oddVerts = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            if (degree[i] % 2 == 1) oddVerts.add(i);
        }
        
        List<List<Integer>> paths = new ArrayList<>();
        int[] adjPtr = new int[n];
        
        if (oddVerts.isEmpty()) {
            // Find Eulerian circuit
            List<Integer> circuit = findPath(0, adj, usedEdge, adjPtr);
            if (!circuit.isEmpty()) paths.add(circuit);
        } else {
            // Start paths from odd-degree vertices
            for (int start : oddVerts) {
                List<Integer> path = findPath(start, adj, usedEdge, adjPtr);
                if (path.size() > 1) paths.add(path);
            }
        }
        
        // Handle remaining cycles (edges not yet used)
        for (int i = 0; i < n; i++) {
            List<Integer> cycle = findPath(i, adj, usedEdge, adjPtr);
            if (cycle.size() > 1) paths.add(cycle);
        }
        
        return paths;
    }

    private static List<Integer> findPath(int start, List<List<int[]>> adj, 
                                          boolean[] usedEdge, int[] adjPtr) {
        LinkedList<Integer> path = new LinkedList<>();
        Deque<Integer> stack = new ArrayDeque<>();
        stack.push(start);
        
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
            if (!found) path.addFirst(stack.pop());
        }
        return path;
    }

    public static void main(String[] args) {
        // Path graph: 0-1-2-3-4 (vertices 0,4 are odd)
        System.out.println("=== Path graph 0-1-2-3-4 ===");
        int[][] edges1 = {{0,1},{1,2},{2,3},{3,4}};
        List<List<Integer>> result1 = decomposePaths(5, edges1);
        System.out.println("Paths: " + result1);
        System.out.println("Expected: 1 path (2 odd-degree vertices)\n");

        // Graph with 4 odd-degree vertices → needs 2 paths
        System.out.println("=== Star graph (center=0, leaves=1,2,3) ===");
        int[][] edges2 = {{0,1},{0,2},{0,3}};
        List<List<Integer>> result2 = decomposePaths(4, edges2);
        System.out.println("Paths: " + result2);
        System.out.println("Expected: 2 paths (4 odd-degree vertices → 4/2=2 paths)\n");

        // Even-degree graph → circuits
        System.out.println("=== Triangle 0-1-2-0 ===");
        int[][] edges3 = {{0,1},{1,2},{2,0}};
        // All degree 2 (even) → 1 circuit
        List<List<Integer>> result3 = decomposePaths(3, edges3);
        System.out.println("Circuits: " + result3);
        
        System.out.println("\nTheorem: min paths = max(1, |odd_vertices|/2)");
    }
}
