import java.util.*;

/**
 * Problem 3: Condensation DAG (Component Graph)
 * 
 * After finding SCCs, contract each SCC into a single node.
 * The resulting graph is a DAG (Directed Acyclic Graph).
 * 
 * Properties:
 * - No cycles (by definition of SCC - all cycles are within SCCs)
 * - Can topologically sort the condensation
 * - Useful for: reachability queries, longest path, etc.
 * 
 * Applications:
 * - Finding which components can reach which
 * - Computing dominators
 * - Simplifying dependency graphs
 */
public class Problem03_CondensationDAG {

    public static int[][] buildCondensation(int n, List<List<Integer>> graph) {
        // Find SCCs using Tarjan's
        int[] comp = new int[n]; // comp[v] = which SCC vertex v belongs to
        int[] disc = new int[n], low = new int[n];
        boolean[] onStack = new boolean[n];
        Arrays.fill(disc, -1);
        Deque<Integer> stack = new ArrayDeque<>();
        int[] timer = {0};
        int[] numComps = {0};
        
        for (int i = 0; i < n; i++) {
            if (disc[i] == -1) {
                tarjan(i, graph, disc, low, onStack, stack, comp, timer, numComps);
            }
        }
        
        int numSCC = numComps[0];
        
        // Build condensation graph
        Set<Long> edges = new HashSet<>();
        List<List<Integer>> condensation = new ArrayList<>();
        for (int i = 0; i < numSCC; i++) condensation.add(new ArrayList<>());
        
        for (int u = 0; u < n; u++) {
            for (int v : graph.get(u)) {
                if (comp[u] != comp[v]) {
                    long key = (long)comp[u] * numSCC + comp[v];
                    if (edges.add(key)) {
                        condensation.get(comp[u]).add(comp[v]);
                    }
                }
            }
        }
        
        // Return: [comp mapping, condensation edges]
        // Print results
        System.out.println("Number of SCCs: " + numSCC);
        Map<Integer, List<Integer>> sccMembers = new HashMap<>();
        for (int i = 0; i < n; i++) {
            sccMembers.computeIfAbsent(comp[i], k -> new ArrayList<>()).add(i);
        }
        for (var entry : sccMembers.entrySet()) {
            System.out.println("  SCC " + entry.getKey() + ": " + entry.getValue());
        }
        System.out.println("Condensation edges:");
        for (int i = 0; i < numSCC; i++) {
            for (int j : condensation.get(i)) {
                System.out.println("  " + i + " -> " + j);
            }
        }
        
        return new int[][]{comp};
    }

    private static void tarjan(int u, List<List<Integer>> graph, int[] disc, int[] low,
                               boolean[] onStack, Deque<Integer> stack, int[] comp,
                               int[] timer, int[] numComps) {
        disc[u] = low[u] = timer[0]++;
        stack.push(u);
        onStack[u] = true;
        
        for (int v : graph.get(u)) {
            if (disc[v] == -1) {
                tarjan(v, graph, disc, low, onStack, stack, comp, timer, numComps);
                low[u] = Math.min(low[u], low[v]);
            } else if (onStack[v]) {
                low[u] = Math.min(low[u], disc[v]);
            }
        }
        
        if (low[u] == disc[u]) {
            int id = numComps[0]++;
            while (true) {
                int v = stack.pop();
                onStack[v] = false;
                comp[v] = id;
                if (v == u) break;
            }
        }
    }

    public static void main(String[] args) {
        int n = 8;
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        int[][] edges = {{0,1},{1,2},{2,0},{2,3},{3,4},{4,5},{5,3},{5,6},{6,7}};
        for (int[] e : edges) graph.get(e[0]).add(e[1]);
        
        System.out.println("Condensation DAG");
        System.out.println("Original edges: " + Arrays.deepToString(edges));
        System.out.println();
        buildCondensation(n, graph);
    }
}
