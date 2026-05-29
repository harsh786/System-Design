import java.util.*;

/**
 * Problem: Lexicographically Smallest Topological Order
 *
 * Approach: Kahn's with min-heap instead of queue
 *
 * Time Complexity: O((V + E) log V)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Choosing deterministic execution order among equally-valid candidates.
 */
public class Problem16_LexicographicallySmallestTopologicalOrder {

    public List<Integer> smallestOrder(int n, int[][] edges) {
        List<List<Integer>> graph = new ArrayList<>();
        int[] inDeg = new int[n];
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); inDeg[e[1]]++; }

        PriorityQueue<Integer> pq = new PriorityQueue<>();
        for (int i = 0; i < n; i++) if (inDeg[i] == 0) pq.offer(i);

        List<Integer> result = new ArrayList<>();
        while (!pq.isEmpty()) {
            int node = pq.poll();
            result.add(node);
            for (int nei : graph.get(node))
                if (--inDeg[nei] == 0) pq.offer(nei);
        }
        return result.size() == n ? result : Collections.emptyList();
    }

    public static void main(String[] args) {
        Problem16_LexicographicallySmallestTopologicalOrder solver = new Problem16_LexicographicallySmallestTopologicalOrder();
        System.out.println(solver.smallestOrder(4, new int[][]{{3,0},{1,0},{2,1}}));
    }
}
