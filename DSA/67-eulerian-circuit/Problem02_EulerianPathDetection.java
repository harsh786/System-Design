import java.util.*;

/**
 * Problem 2: Eulerian Path Detection
 * 
 * An Eulerian Path visits every EDGE exactly once.
 * 
 * Conditions for Eulerian Path in DIRECTED graph:
 * 1. Graph is connected (weakly - ignoring directions)
 * 2. At most one vertex has outDegree - inDegree = 1 (start)
 * 3. At most one vertex has inDegree - outDegree = 1 (end)
 * 4. All other vertices have inDegree == outDegree
 * 
 * Conditions for Eulerian Path in UNDIRECTED graph:
 * 1. Graph is connected
 * 2. Exactly 0 or 2 vertices have odd degree
 *    - 0 odd: Eulerian circuit exists (path that returns to start)
 *    - 2 odd: Eulerian path exists between the two odd-degree vertices
 */
public class Problem02_EulerianPathDetection {

    // Directed graph Eulerian path detection
    public static int[] hasEulerianPathDirected(int n, int[][] edges) {
        int[] inDeg = new int[n], outDeg = new int[n];
        List<List<Integer>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        
        for (int[] e : edges) {
            outDeg[e[0]]++;
            inDeg[e[1]]++;
            adj.get(e[0]).add(e[1]);
        }
        
        int startNodes = 0, endNodes = 0;
        int start = 0;
        for (int i = 0; i < n; i++) {
            int diff = outDeg[i] - inDeg[i];
            if (diff == 1) { startNodes++; start = i; }
            else if (diff == -1) endNodes++;
            else if (diff != 0) return null; // No Eulerian path
        }
        
        // Check: either all balanced (circuit) or exactly one start and one end
        if (!((startNodes == 0 && endNodes == 0) || (startNodes == 1 && endNodes == 1))) {
            return null;
        }
        
        // Check connectivity (BFS from start)
        boolean[] visited = new boolean[n];
        Queue<Integer> queue = new LinkedList<>();
        queue.offer(start);
        visited[start] = true;
        while (!queue.isEmpty()) {
            int u = queue.poll();
            for (int v : adj.get(u)) {
                if (!visited[v]) { visited[v] = true; queue.offer(v); }
            }
        }
        // All nodes with edges should be reachable
        for (int i = 0; i < n; i++) {
            if (!visited[i] && (inDeg[i] > 0 || outDeg[i] > 0)) return null;
        }
        
        return new int[]{start, startNodes == 0 ? 1 : 0}; // [startNode, isCircuit]
    }

    // Undirected graph Eulerian path detection
    public static boolean hasEulerianPathUndirected(int n, int[][] edges) {
        int[] degree = new int[n];
        int[] parent = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        
        for (int[] e : edges) {
            degree[e[0]]++;
            degree[e[1]]++;
            union(parent, e[0], e[1]);
        }
        
        // Check connectivity
        int components = 0;
        for (int i = 0; i < n; i++) {
            if (degree[i] > 0 && find(parent, i) == i) components++;
        }
        if (components > 1) return false;
        
        // Count odd degree vertices
        int oddCount = 0;
        for (int d : degree) if (d % 2 != 0) oddCount++;
        
        return oddCount == 0 || oddCount == 2;
    }

    private static int find(int[] parent, int x) {
        while (parent[x] != x) { parent[x] = parent[parent[x]]; x = parent[x]; }
        return x;
    }
    private static void union(int[] parent, int a, int b) {
        parent[find(parent, a)] = find(parent, b);
    }

    public static void main(String[] args) {
        // Directed: 0->1->2->0->3->4 (has Eulerian path from 0 to 4)
        int[][] directed = {{0,1},{1,2},{2,0},{0,3},{3,4}};
        int[] result = hasEulerianPathDirected(5, directed);
        System.out.println("Directed graph: " + (result != null ? 
            "Eulerian path exists, start=" + result[0] + ", circuit=" + (result[1]==1) : "No path"));

        // Undirected: triangle + tail
        int[][] undirected = {{0,1},{1,2},{2,0},{0,3}};
        System.out.println("Undirected graph: Eulerian path exists = " + 
            hasEulerianPathUndirected(4, undirected));
    }
}
