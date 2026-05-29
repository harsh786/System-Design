import java.util.*;

/**
 * Problem 6: Minimum Number of Vertices to Reach All Nodes (LeetCode 1557)
 * 
 * Find the smallest set of vertices from which all other vertices are reachable.
 * 
 * Key insight: The answer is all vertices with in-degree 0.
 * - Nodes with in-degree 0 MUST be in the answer (no other node can reach them)
 * - Nodes with in-degree > 0 can be reached from their predecessors
 * 
 * For general graphs (with cycles), use SCC condensation:
 * - Source SCCs in the condensation DAG (in-degree 0) must be included
 * - Pick one node from each source SCC
 * 
 * Time: O(V + E)
 */
public class Problem06_MinVerticesReachAll {

    // Simple version for DAG (LeetCode 1557 - guaranteed no cycles)
    public static List<Integer> findSmallestSetOfVertices(int n, List<List<Integer>> edges) {
        boolean[] hasIncoming = new boolean[n];
        for (List<Integer> edge : edges) {
            hasIncoming[edge.get(1)] = true;
        }
        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            if (!hasIncoming[i]) result.add(i);
        }
        return result;
    }

    // General version using SCC condensation (works with cycles)
    public static List<Integer> findMinVerticesGeneral(int n, List<List<Integer>> graph) {
        // Find SCCs
        int[] comp = new int[n];
        int[] disc = new int[n], low = new int[n];
        boolean[] onStack = new boolean[n];
        Arrays.fill(disc, -1);
        Deque<Integer> stack = new ArrayDeque<>();
        int[] state = {0, 0}; // timer, numComps
        
        for (int i = 0; i < n; i++)
            if (disc[i] == -1) tarjan(i, graph, disc, low, onStack, stack, comp, state);
        
        int numSCC = state[1];
        
        // Find in-degree of each SCC in condensation
        boolean[] hasIncoming = new boolean[numSCC];
        for (int u = 0; u < n; u++) {
            for (int v : graph.get(u)) {
                if (comp[u] != comp[v]) {
                    hasIncoming[comp[v]] = true;
                }
            }
        }
        
        // Pick one representative from each source SCC
        List<Integer> result = new ArrayList<>();
        boolean[] picked = new boolean[numSCC];
        for (int i = 0; i < n; i++) {
            if (!hasIncoming[comp[i]] && !picked[comp[i]]) {
                result.add(i);
                picked[comp[i]] = true;
            }
        }
        return result;
    }

    private static void tarjan(int u, List<List<Integer>> graph, int[] disc, int[] low,
                               boolean[] onStack, Deque<Integer> stack, int[] comp, int[] state) {
        disc[u] = low[u] = state[0]++;
        stack.push(u);
        onStack[u] = true;
        for (int v : graph.get(u)) {
            if (disc[v] == -1) { tarjan(v, graph, disc, low, onStack, stack, comp, state); low[u] = Math.min(low[u], low[v]); }
            else if (onStack[v]) low[u] = Math.min(low[u], disc[v]);
        }
        if (low[u] == disc[u]) {
            int id = state[1]++;
            while (true) { int v = stack.pop(); onStack[v] = false; comp[v] = id; if (v == u) break; }
        }
    }

    public static void main(String[] args) {
        // DAG example
        int n = 6;
        List<List<Integer>> edges = Arrays.asList(
            Arrays.asList(0,1), Arrays.asList(0,2), Arrays.asList(2,5),
            Arrays.asList(3,0), Arrays.asList(3,2), Arrays.asList(4,2), Arrays.asList(4,5));
        System.out.println("LeetCode 1557: Min vertices to reach all");
        System.out.println("DAG result: " + findSmallestSetOfVertices(n, edges));
        // Expected: [3, 4]

        // General graph with cycles
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < 6; i++) graph.add(new ArrayList<>());
        graph.get(0).add(1); graph.get(1).add(2); graph.get(2).add(0); // cycle 0-1-2
        graph.get(3).add(4); graph.get(4).add(3); // cycle 3-4
        graph.get(2).add(3); // bridge from cycle1 to cycle2
        graph.get(5).add(4); // 5 points to cycle2
        System.out.println("General graph result: " + findMinVerticesGeneral(6, graph));
    }
}
