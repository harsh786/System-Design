import java.util.*;

/**
 * Problem 2: Tarjan's Algorithm for SCC
 * 
 * Single-pass DFS algorithm using a stack and low-link values.
 * 
 * Key concepts:
 * - disc[u]: discovery time of node u
 * - low[u]: lowest discovery time reachable from subtree of u
 * - A node u is root of SCC if low[u] == disc[u]
 * 
 * Algorithm:
 * 1. DFS, maintain stack of visited nodes
 * 2. For each node, compute low-link value
 * 3. When low[u] == disc[u], pop all nodes from stack until u → that's the SCC
 * 
 * Time: O(V + E), Space: O(V)
 * Advantage over Kosaraju: single pass, no need to build transpose
 */
public class Problem02_TarjanSCC {

    private int timer = 0;
    private int[] disc, low;
    private boolean[] onStack;
    private Deque<Integer> stack;
    private List<List<Integer>> sccs;
    private List<List<Integer>> graph;

    public List<List<Integer>> findSCCs(int n, List<List<Integer>> graph) {
        this.graph = graph;
        disc = new int[n];
        low = new int[n];
        onStack = new boolean[n];
        Arrays.fill(disc, -1);
        stack = new ArrayDeque<>();
        sccs = new ArrayList<>();

        for (int i = 0; i < n; i++) {
            if (disc[i] == -1) tarjanDFS(i);
        }
        return sccs;
    }

    private void tarjanDFS(int u) {
        disc[u] = low[u] = timer++;
        stack.push(u);
        onStack[u] = true;

        for (int v : graph.get(u)) {
            if (disc[v] == -1) {
                tarjanDFS(v);
                low[u] = Math.min(low[u], low[v]);
            } else if (onStack[v]) {
                // Back edge to ancestor in current SCC
                low[u] = Math.min(low[u], disc[v]);
            }
        }

        // If u is root of an SCC
        if (low[u] == disc[u]) {
            List<Integer> scc = new ArrayList<>();
            while (true) {
                int v = stack.pop();
                onStack[v] = false;
                scc.add(v);
                if (v == u) break;
            }
            sccs.add(scc);
        }
    }

    public static void main(String[] args) {
        int n = 7;
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        
        // Classic example with 3 SCCs: {0,1,2}, {3,4}, {5,6}
        int[][] edges = {{0,1},{1,2},{2,0},{1,3},{3,4},{4,3},{4,5},{5,6},{6,5}};
        for (int[] e : edges) graph.get(e[0]).add(e[1]);

        Problem02_TarjanSCC solver = new Problem02_TarjanSCC();
        List<List<Integer>> sccs = solver.findSCCs(n, graph);

        System.out.println("Tarjan's Algorithm - SCCs");
        System.out.println("Number of SCCs: " + sccs.size());
        for (List<Integer> scc : sccs) {
            System.out.println("  SCC: " + scc);
        }
    }
}
