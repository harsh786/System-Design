import java.util.*;

/**
 * Problem: Path with Maximum Probability
 * Find path with maximum success probability from start to end.
 *
 * Approach: Modified Dijkstra with max-heap (maximize product of probabilities)
 *
 * Time Complexity: O((V + E) log V)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Finding most reliable network path (maximize uptime product).
 */
public class Problem18_PathWithMaximumProbability {

    public double maxProbability(int n, int[][] edges, double[] succProb, int start, int end) {
        List<double[]>[] graph = new List[n];
        for (int i = 0; i < n; i++) graph[i] = new ArrayList<>();
        for (int i = 0; i < edges.length; i++) {
            graph[edges[i][0]].add(new double[]{edges[i][1], succProb[i]});
            graph[edges[i][1]].add(new double[]{edges[i][0], succProb[i]});
        }

        double[] prob = new double[n];
        prob[start] = 1.0;
        PriorityQueue<double[]> pq = new PriorityQueue<>((a, b) -> Double.compare(b[1], a[1]));
        pq.offer(new double[]{start, 1.0});

        while (!pq.isEmpty()) {
            double[] cur = pq.poll();
            int u = (int) cur[0];
            if (u == end) return cur[1];
            if (cur[1] < prob[u]) continue;
            for (double[] nei : graph[u]) {
                int v = (int) nei[0];
                double newProb = prob[u] * nei[1];
                if (newProb > prob[v]) { prob[v] = newProb; pq.offer(new double[]{v, newProb}); }
            }
        }
        return 0.0;
    }

    public static void main(String[] args) {
        Problem18_PathWithMaximumProbability solver = new Problem18_PathWithMaximumProbability();
        System.out.println(solver.maxProbability(3, new int[][]{{0,1},{1,2},{0,2}}, new double[]{0.5,0.5,0.2}, 0, 2)); // 0.25
    }
}
