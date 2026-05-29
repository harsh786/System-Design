import java.util.*;

/**
 * Problem: DFS Topological Sort
 * Classic DFS-based topological sort using post-order reversal.
 *
 * Approach: DFS, push to stack after visiting all descendants
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V)
 *
 * Production Analogy: Resolving symbol dependencies in a linker.
 */
public class Problem15_DFSTopologicalSort {

    public List<Integer> topologicalSort(int n, int[][] edges) {
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) graph.get(e[0]).add(e[1]);

        boolean[] visited = new boolean[n];
        Deque<Integer> stack = new ArrayDeque<>();

        for (int i = 0; i < n; i++)
            if (!visited[i]) dfs(graph, i, visited, stack);

        return new ArrayList<>(stack);
    }

    private void dfs(List<List<Integer>> graph, int node, boolean[] visited, Deque<Integer> stack) {
        visited[node] = true;
        for (int nei : graph.get(node))
            if (!visited[nei]) dfs(graph, nei, visited, stack);
        stack.push(node);
    }

    public static void main(String[] args) {
        Problem15_DFSTopologicalSort solver = new Problem15_DFSTopologicalSort();
        System.out.println(solver.topologicalSort(6, new int[][]{{5,2},{5,0},{4,0},{4,1},{2,3},{3,1}}));
    }
}
