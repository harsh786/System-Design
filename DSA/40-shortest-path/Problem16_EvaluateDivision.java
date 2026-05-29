import java.util.*;

/**
 * Problem: Evaluate Division (Weighted Graph)
 * Given equations a/b=k, answer queries a/c.
 *
 * Approach: Build weighted graph, BFS/DFS to find path and multiply weights
 *
 * Time Complexity: O(Q * (V + E))
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Currency conversion through intermediate exchange rates.
 */
public class Problem16_EvaluateDivision {

    public double[] calcEquation(List<List<String>> equations, double[] values, List<List<String>> queries) {
        Map<String, Map<String, Double>> graph = new HashMap<>();
        for (int i = 0; i < equations.size(); i++) {
            String a = equations.get(i).get(0), b = equations.get(i).get(1);
            graph.computeIfAbsent(a, k -> new HashMap<>()).put(b, values[i]);
            graph.computeIfAbsent(b, k -> new HashMap<>()).put(a, 1.0 / values[i]);
        }

        double[] result = new double[queries.size()];
        for (int i = 0; i < queries.size(); i++) {
            String src = queries.get(i).get(0), dst = queries.get(i).get(1);
            if (!graph.containsKey(src) || !graph.containsKey(dst)) { result[i] = -1; continue; }
            result[i] = bfs(graph, src, dst);
        }
        return result;
    }

    private double bfs(Map<String, Map<String, Double>> graph, String src, String dst) {
        if (src.equals(dst)) return 1.0;
        Queue<String[]> q = new LinkedList<>();
        Queue<Double> vals = new LinkedList<>();
        Set<String> visited = new HashSet<>();
        q.offer(new String[]{src}); vals.offer(1.0); visited.add(src);
        while (!q.isEmpty()) {
            String cur = q.poll()[0]; double val = vals.poll();
            for (var e : graph.get(cur).entrySet()) {
                if (e.getKey().equals(dst)) return val * e.getValue();
                if (visited.add(e.getKey())) { q.offer(new String[]{e.getKey()}); vals.offer(val * e.getValue()); }
            }
        }
        return -1.0;
    }

    public static void main(String[] args) {
        Problem16_EvaluateDivision solver = new Problem16_EvaluateDivision();
        List<List<String>> eq = Arrays.asList(Arrays.asList("a","b"), Arrays.asList("b","c"));
        List<List<String>> queries = Arrays.asList(Arrays.asList("a","c"), Arrays.asList("b","a"));
        System.out.println(Arrays.toString(solver.calcEquation(eq, new double[]{2.0, 3.0}, queries)));
    }
}
