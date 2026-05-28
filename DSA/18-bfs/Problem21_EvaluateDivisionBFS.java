import java.util.*;

/**
 * Problem: Evaluate Division BFS (LeetCode 399)
 * Approach: BFS through weighted graph multiplying edge weights along path
 * Time: O(Q*(V+E)), Space: O(V+E)
 * Production Analogy: Currency conversion via BFS through exchange rate graph
 */
public class Problem21_EvaluateDivisionBFS {
    public double[] calcEquation(List<List<String>> equations, double[] values, List<List<String>> queries) {
        Map<String, Map<String, Double>> graph = new HashMap<>();
        for (int i = 0; i < equations.size(); i++) {
            String a = equations.get(i).get(0), b = equations.get(i).get(1);
            graph.computeIfAbsent(a, k -> new HashMap<>()).put(b, values[i]);
            graph.computeIfAbsent(b, k -> new HashMap<>()).put(a, 1.0 / values[i]);
        }
        double[] res = new double[queries.size()];
        for (int i = 0; i < queries.size(); i++)
            res[i] = bfs(graph, queries.get(i).get(0), queries.get(i).get(1));
        return res;
    }

    private double bfs(Map<String, Map<String, Double>> graph, String src, String dst) {
        if (!graph.containsKey(src) || !graph.containsKey(dst)) return -1.0;
        if (src.equals(dst)) return 1.0;
        Queue<String[]> q = new LinkedList<>(); // [node, product]
        Queue<Double> vals = new LinkedList<>();
        Set<String> visited = new HashSet<>();
        q.offer(new String[]{src}); vals.offer(1.0); visited.add(src);
        while (!q.isEmpty()) {
            String curr = q.poll()[0]; double val = vals.poll();
            for (Map.Entry<String, Double> e : graph.get(curr).entrySet()) {
                if (e.getKey().equals(dst)) return val * e.getValue();
                if (visited.add(e.getKey())) { q.offer(new String[]{e.getKey()}); vals.offer(val * e.getValue()); }
            }
        }
        return -1.0;
    }

    public static void main(String[] args) {
        List<List<String>> eq = Arrays.asList(Arrays.asList("a","b"), Arrays.asList("b","c"));
        List<List<String>> queries = Arrays.asList(Arrays.asList("a","c"), Arrays.asList("b","a"));
        System.out.println(Arrays.toString(new Problem21_EvaluateDivisionBFS().calcEquation(eq, new double[]{2.0,3.0}, queries)));
    }
}
