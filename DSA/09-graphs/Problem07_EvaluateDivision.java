import java.util.*;

/**
 * Problem 7: Evaluate Division (LeetCode 399)
 * 
 * Approach: Build weighted directed graph, BFS/DFS to find path and multiply weights.
 * Time: O(Q * (V + E)), Space: O(V + E)
 * 
 * Production Analogy: Currency exchange rate computation through intermediate currencies.
 */
public class Problem07_EvaluateDivision {
    
    public double[] calcEquation(List<List<String>> equations, double[] values, List<List<String>> queries) {
        Map<String, Map<String, Double>> graph = new HashMap<>();
        for (int i = 0; i < equations.size(); i++) {
            String a = equations.get(i).get(0), b = equations.get(i).get(1);
            graph.computeIfAbsent(a, k -> new HashMap<>()).put(b, values[i]);
            graph.computeIfAbsent(b, k -> new HashMap<>()).put(a, 1.0 / values[i]);
        }
        double[] res = new double[queries.size()];
        for (int i = 0; i < queries.size(); i++) {
            String src = queries.get(i).get(0), dst = queries.get(i).get(1);
            if (!graph.containsKey(src) || !graph.containsKey(dst)) { res[i] = -1.0; continue; }
            res[i] = bfs(graph, src, dst);
        }
        return res;
    }
    
    private double bfs(Map<String, Map<String, Double>> graph, String src, String dst) {
        if (src.equals(dst)) return 1.0;
        Queue<String[]> q = new LinkedList<>(); // [node, accumulated product as string]
        Queue<Double> weights = new LinkedList<>();
        Set<String> visited = new HashSet<>();
        q.offer(new String[]{src}); weights.offer(1.0); visited.add(src);
        while (!q.isEmpty()) {
            String node = q.poll()[0]; double w = weights.poll();
            for (var e : graph.get(node).entrySet()) {
                if (e.getKey().equals(dst)) return w * e.getValue();
                if (visited.add(e.getKey())) { q.offer(new String[]{e.getKey()}); weights.offer(w * e.getValue()); }
            }
        }
        return -1.0;
    }
    
    public static void main(String[] args) {
        Problem07_EvaluateDivision sol = new Problem07_EvaluateDivision();
        List<List<String>> eq = Arrays.asList(Arrays.asList("a","b"), Arrays.asList("b","c"));
        double[] vals = {2.0, 3.0};
        List<List<String>> queries = Arrays.asList(Arrays.asList("a","c"), Arrays.asList("b","a"), Arrays.asList("a","e"), Arrays.asList("a","a"));
        System.out.println(Arrays.toString(sol.calcEquation(eq, vals, queries))); // [6.0, 0.5, -1.0, 1.0]
    }
}
