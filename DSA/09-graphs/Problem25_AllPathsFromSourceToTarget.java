import java.util.*;

/**
 * Problem 25: All Paths From Source to Target (LeetCode 797)
 * 
 * Approach: DFS/backtracking on DAG. No need for visited since it's a DAG.
 * Time: O(2^N * N), Space: O(N) recursion depth
 * 
 * Production Analogy: Enumerating all possible request flows from entry gateway to final service.
 */
public class Problem25_AllPathsFromSourceToTarget {
    
    public List<List<Integer>> allPathsSourceTarget(int[][] graph) {
        List<List<Integer>> result = new ArrayList<>();
        List<Integer> path = new ArrayList<>();
        path.add(0);
        dfs(graph, 0, graph.length - 1, path, result);
        return result;
    }
    
    void dfs(int[][] graph, int node, int target, List<Integer> path, List<List<Integer>> result) {
        if (node == target) { result.add(new ArrayList<>(path)); return; }
        for (int next : graph[node]) {
            path.add(next);
            dfs(graph, next, target, path, result);
            path.remove(path.size() - 1);
        }
    }
    
    public static void main(String[] args) {
        Problem25_AllPathsFromSourceToTarget sol = new Problem25_AllPathsFromSourceToTarget();
        System.out.println(sol.allPathsSourceTarget(new int[][]{{1,2},{3},{3},{}})); // [[0,1,3],[0,2,3]]
        System.out.println(sol.allPathsSourceTarget(new int[][]{{4,3,1},{3,2,4},{3},{4},{}})); 
    }
}
