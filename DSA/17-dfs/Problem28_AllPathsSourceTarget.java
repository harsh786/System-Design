import java.util.*;

/**
 * Problem: All Paths From Source to Target (LeetCode 797)
 * Approach: DFS backtracking on DAG (no cycle check needed)
 * Time: O(2^N * N), Space: O(N)
 * Production Analogy: Enumerating all possible request flows through a service mesh
 */
public class Problem28_AllPathsSourceTarget {
    public List<List<Integer>> allPathsSourceTarget(int[][] graph) {
        List<List<Integer>> res = new ArrayList<>();
        List<Integer> path = new ArrayList<>();
        path.add(0);
        dfs(graph, 0, path, res);
        return res;
    }

    private void dfs(int[][] graph, int node, List<Integer> path, List<List<Integer>> res) {
        if (node == graph.length - 1) { res.add(new ArrayList<>(path)); return; }
        for (int next : graph[node]) {
            path.add(next);
            dfs(graph, next, path, res);
            path.remove(path.size() - 1);
        }
    }

    public static void main(String[] args) {
        int[][] graph = {{1,2},{3},{3},{}};
        System.out.println(new Problem28_AllPathsSourceTarget().allPathsSourceTarget(graph));
    }
}
