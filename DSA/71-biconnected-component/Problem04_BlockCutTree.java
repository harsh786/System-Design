import java.util.*;

/**
 * Problem 4: Block-Cut Tree
 * 
 * The Block-Cut Tree represents the structure of biconnected components:
 * - Block nodes: one per biconnected component
 * - Cut nodes: one per articulation point
 * - Edges: between a block and cut vertex if the cut vertex belongs to that block
 * 
 * Properties:
 * - The block-cut tree is always a tree (forest if graph disconnected)
 * - Useful for answering path queries: "must path from u to v pass through vertex w?"
 * - Two vertices are in the same biconnected component iff removing any single
 *   vertex keeps them connected
 * 
 * Time: O(V + E) to construct
 */
public class Problem04_BlockCutTree {

    private int timer = 0;
    private List<Set<Integer>> blocks = new ArrayList<>(); // Each block contains vertices
    private Set<Integer> cutVertices = new HashSet<>();

    public void buildBlockCutTree(int n, List<List<Integer>> adj) {
        int[] disc = new int[n], low = new int[n];
        boolean[] visited = new boolean[n];
        Deque<Integer> vertexStack = new ArrayDeque<>();

        for (int i = 0; i < n; i++) {
            if (!visited[i]) dfs(i, -1, adj, disc, low, visited, vertexStack);
        }
    }

    private void dfs(int u, int parent, List<List<Integer>> adj,
                     int[] disc, int[] low, boolean[] visited, Deque<Integer> stack) {
        visited[u] = true;
        disc[u] = low[u] = timer++;
        stack.push(u);
        int children = 0;

        for (int v : adj.get(u)) {
            if (!visited[v]) {
                children++;
                dfs(v, u, adj, disc, low, visited, stack);
                low[u] = Math.min(low[u], low[v]);

                boolean isAP = (parent == -1 && children > 1) || (parent != -1 && low[v] >= disc[u]);
                if (isAP || (parent == -1 && children == 1 && adj.get(u).size() == children)) {
                    if (low[v] >= disc[u]) {
                        Set<Integer> block = new HashSet<>();
                        while (stack.peek() != v) block.add(stack.pop());
                        block.add(stack.pop()); // pop v
                        block.add(u); // u is part of this block but stays on stack
                        blocks.add(block);
                        if (parent != -1 || children > 1) cutVertices.add(u);
                    }
                }
            } else if (v != parent) {
                low[u] = Math.min(low[u], disc[v]);
            }
        }

        // If u is root and processed, remaining vertices on stack form a block
        if (parent == -1 && !stack.isEmpty()) {
            Set<Integer> block = new HashSet<>();
            while (!stack.isEmpty()) block.add(stack.pop());
            if (block.size() > 0) blocks.add(block);
        }
    }

    public static void main(String[] args) {
        int n = 7;
        List<List<Integer>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        // Two triangles connected at vertex 2, with a pendant at 6
        int[][] edges = {{0,1},{1,2},{2,0},{2,3},{3,4},{4,2},{4,5},{5,6}};
        for (int[] e : edges) { adj.get(e[0]).add(e[1]); adj.get(e[1]).add(e[0]); }

        Problem04_BlockCutTree solver = new Problem04_BlockCutTree();
        solver.buildBlockCutTree(n, adj);

        System.out.println("Block-Cut Tree");
        System.out.println("Edges: " + Arrays.deepToString(edges));
        System.out.println("\nBlocks (biconnected components):");
        for (int i = 0; i < solver.blocks.size(); i++) {
            System.out.println("  Block " + i + ": " + solver.blocks.get(i));
        }
        System.out.println("Cut vertices: " + solver.cutVertices);
        System.out.println("\nBlock-Cut Tree structure:");
        System.out.println("  Each cut vertex connects adjacent blocks");
    }
}
