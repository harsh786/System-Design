import java.util.*;

/**
 * Problem 6: Eulerian Path in Undirected Graph
 * 
 * Find a path that traverses every edge exactly once in an undirected graph.
 * 
 * Conditions:
 * - Graph must be connected (considering only vertices with edges)
 * - Either 0 or 2 vertices have odd degree
 *   - 0 odd: start anywhere (Eulerian circuit)
 *   - 2 odd: start at one odd-degree vertex, end at the other
 * 
 * Uses Hierholzer's algorithm adapted for undirected graphs:
 * - Must track edge usage (not just adjacency) since each edge can be traversed once
 */
public class Problem06_EulerianPathUndirected {

    public static List<Integer> findEulerianPath(int n, int[][] edges) {
        // Build adjacency with edge indices
        List<List<int[]>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        boolean[] usedEdge = new boolean[edges.length];
        int[] degree = new int[n];
        
        for (int i = 0; i < edges.length; i++) {
            int u = edges[i][0], v = edges[i][1];
            adj.get(u).add(new int[]{v, i});
            adj.get(v).add(new int[]{u, i});
            degree[u]++;
            degree[v]++;
        }
        
        // Find start vertex
        int start = 0;
        List<Integer> oddVertices = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            if (degree[i] % 2 == 1) oddVertices.add(i);
        }
        
        if (oddVertices.size() != 0 && oddVertices.size() != 2) {
            System.out.println("No Eulerian path exists (" + oddVertices.size() + " odd-degree vertices)");
            return null;
        }
        if (oddVertices.size() == 2) start = oddVertices.get(0);
        
        // Track position in adjacency list for each vertex
        int[] adjPtr = new int[n];
        
        // Hierholzer's with edge tracking
        LinkedList<Integer> path = new LinkedList<>();
        Deque<Integer> stack = new ArrayDeque<>();
        stack.push(start);
        
        while (!stack.isEmpty()) {
            int v = stack.peek();
            boolean found = false;
            while (adjPtr[v] < adj.get(v).size()) {
                int[] edge = adj.get(v).get(adjPtr[v]);
                adjPtr[v]++;
                if (!usedEdge[edge[1]]) {
                    usedEdge[edge[1]] = true;
                    stack.push(edge[0]);
                    found = true;
                    break;
                }
            }
            if (!found) {
                path.addFirst(stack.pop());
            }
        }
        
        if (path.size() != edges.length + 1) {
            System.out.println("Graph is not connected");
            return null;
        }
        return path;
    }

    public static void main(String[] args) {
        // Königsberg bridge-like graph (no Euler path - 4 odd vertices)
        System.out.println("=== Königsberg Bridges (no Euler path) ===");
        int[][] konigsberg = {{0,1},{0,1},{0,2},{0,2},{1,2},{1,3},{2,3}};
        findEulerianPath(4, konigsberg);
        
        // Graph with Euler path (2 odd vertices)
        System.out.println("\n=== Graph with Eulerian Path ===");
        int[][] edges = {{0,1},{1,2},{2,0},{0,3},{3,4},{4,0}};
        List<Integer> path = findEulerianPath(5, edges);
        if (path != null) System.out.println("Eulerian path: " + path);
        
        // Graph with Euler circuit (all even degree)
        System.out.println("\n=== Graph with Eulerian Circuit ===");
        int[][] circuit = {{0,1},{1,2},{2,3},{3,0},{0,2},{1,3}};
        List<Integer> circuitPath = findEulerianPath(4, circuit);
        if (circuitPath != null) {
            System.out.println("Eulerian circuit: " + circuitPath);
            System.out.println("Returns to start: " + 
                (circuitPath.get(0).equals(circuitPath.get(circuitPath.size()-1))));
        }
    }
}
