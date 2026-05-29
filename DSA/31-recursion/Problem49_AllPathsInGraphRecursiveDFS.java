import java.util.*;

public class Problem49_AllPathsInGraphRecursiveDFS {
    public static List<List<Integer>> allPathsSourceTarget(int[][] graph) {
        List<List<Integer>> res = new ArrayList<>();
        List<Integer> path = new ArrayList<>();
        path.add(0);
        dfs(graph, 0, path, res);
        return res;
    }
    static void dfs(int[][] graph, int node, List<Integer> path, List<List<Integer>> res) {
        if (node == graph.length - 1) { res.add(new ArrayList<>(path)); return; }
        for (int next : graph[node]) {
            path.add(next); dfs(graph, next, path, res); path.remove(path.size() - 1);
        }
    }
    public static void main(String[] args) {
        int[][] graph = {{1,2},{3},{3},{}};
        System.out.println(allPathsSourceTarget(graph)); // [[0,1,3],[0,2,3]]
    }
}
