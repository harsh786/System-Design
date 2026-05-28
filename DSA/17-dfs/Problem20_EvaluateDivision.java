import java.util.*;

/**
 * Problem: Evaluate Division (LeetCode 399)
 * Approach: Build weighted directed graph, DFS to find path and multiply weights
 * Time: O(Q*(V+E)), Space: O(V+E)
 * Production Analogy: Currency conversion through intermediate exchange rates
 */
public class Problem20_EvaluateDivision {
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
            if (!graph.containsKey(src) || !graph.containsKey(dst)) res[i] = -1.0;
            else res[i] = dfs(graph, src, dst, new HashSet<>());
        }
        return res;
    }

    private double dfs(Map<String, Map<String, Double>> graph, String src, String dst, Set<String> visited) {
        if (src.equals(dst)) return 1.0;
        visited.add(src);
        for (Map.Entry<String, Double> e : graph.get(src).entrySet()) {
            if (visited.contains(e.getKey())) continue;
            double result = dfs(graph, e.getKey(), dst, visited);
            if (result != -1.0) return e.getValue() * result;
        }
        return -1.0;
    }

    public static void main(String[] args) {
        List<List<String>> eq = Arrays.asList(Arrays.asList("a","b"), Arrays.asList("b","c"));
        double[] vals = {2.0, 3.0};
        List<List<String>> queries = Arrays.asList(Arrays.asList("a","c"), Arrays.asList("b","a"));
        System.out.println(Arrays.toString(new Problem20_EvaluateDivision().calcEquation(eq, vals, queries)));
    }
}
