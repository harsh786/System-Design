import java.util.*;

/**
 * Problem 1: Kosaraju's Algorithm for Strongly Connected Components
 * 
 * A Strongly Connected Component (SCC) is a maximal set of vertices such that
 * there is a path from each vertex to every other vertex in the set.
 * 
 * Kosaraju's Algorithm (two-pass DFS):
 * 1. Run DFS on original graph, push vertices to stack in finish order
 * 2. Transpose the graph (reverse all edges)
 * 3. Pop vertices from stack, run DFS on transposed graph
 *    Each DFS tree in step 3 is one SCC
 * 
 * Time: O(V + E), Space: O(V + E)
 * 
 * Why it works: In the transpose graph, vertices in the same SCC remain connected,
 * but cross-SCC edges are reversed. Processing in reverse finish order ensures
 * we start DFS from the "source" SCCs in the condensation DAG.
 */
public class Problem01_KosarajuSCC {

    public static List<List<Integer>> findSCCs(int n, List<List<Integer>> graph) {
        // Step 1: DFS on original graph, record finish order
        boolean[] visited = new boolean[n];
        Deque<Integer> stack = new ArrayDeque<>();
        for (int i = 0; i < n; i++) {
            if (!visited[i]) dfs1(i, graph, visited, stack);
        }
        
        // Step 2: Build transpose graph
        List<List<Integer>> transpose = new ArrayList<>();
        for (int i = 0; i < n; i++) transpose.add(new ArrayList<>());
        for (int u = 0; u < n; u++) {
            for (int v : graph.get(u)) {
                transpose.get(v).add(u);
            }
        }
        
        // Step 3: DFS on transpose in reverse finish order
        Arrays.fill(visited, false);
        List<List<Integer>> sccs = new ArrayList<>();
        while (!stack.isEmpty()) {
            int v = stack.pop();
            if (!visited[v]) {
                List<Integer> component = new ArrayList<>();
                dfs2(v, transpose, visited, component);
                sccs.add(component);
            }
        }
        return sccs;
    }

    private static void dfs1(int u, List<List<Integer>> graph, boolean[] visited, Deque<Integer> stack) {
        visited[u] = true;
        for (int v : graph.get(u)) {
            if (!visited[v]) dfs1(v, graph, visited, stack);
        }
        stack.push(u); // Push on finish
    }

    private static void dfs2(int u, List<List<Integer>> graph, boolean[] visited, List<Integer> component) {
        visited[u] = true;
        component.add(u);
        for (int v : graph.get(u)) {
            if (!visited[v]) dfs2(v, graph, visited, component);
        }
    }

    public static void main(String[] args) {
        int n = 8;
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        
        // Add edges: two cycles connected
        int[][] edges = {{0,1},{1,2},{2,0},{2,3},{3,4},{4,5},{5,3},{4,6},{6,7},{7,6}};
        for (int[] e : edges) graph.get(e[0]).add(e[1]);
        
        List<List<Integer>> sccs = findSCCs(n, graph);
        
        System.out.println("Kosaraju's Algorithm - Strongly Connected Components");
        System.out.println("Graph: " + Arrays.deepToString(edges));
        System.out.println("Number of SCCs: " + sccs.size());
        for (int i = 0; i < sccs.size(); i++) {
            System.out.println("  SCC " + i + ": " + sccs.get(i));
        }
    }
}
