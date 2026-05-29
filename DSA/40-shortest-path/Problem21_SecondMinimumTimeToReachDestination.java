import java.util.*;

/**
 * Problem: Second Minimum Time to Reach Destination
 *
 * Approach: Modified BFS tracking two shortest times per node
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V)
 *
 * Production Analogy: Finding backup routing time when primary is unavailable.
 */
public class Problem21_SecondMinimumTimeToReachDestination {

    public int secondMinimum(int n, int[][] edges, int time, int change) {
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i <= n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); graph.get(e[1]).add(e[0]); }

        int[] dist1 = new int[n + 1], dist2 = new int[n + 1];
        Arrays.fill(dist1, Integer.MAX_VALUE); Arrays.fill(dist2, Integer.MAX_VALUE);
        dist1[1] = 0;
        Queue<int[]> q = new LinkedList<>();
        q.offer(new int[]{1, 0});

        while (!q.isEmpty()) {
            int[] cur = q.poll();
            int node = cur[0], t = cur[1];
            // Calculate actual time with traffic lights
            int actualTime = t;
            if ((actualTime / change) % 2 == 1) actualTime = (actualTime / change + 1) * change;
            actualTime += time;

            for (int nei : graph.get(node)) {
                if (actualTime < dist1[nei]) {
                    dist2[nei] = dist1[nei]; dist1[nei] = actualTime;
                    q.offer(new int[]{nei, actualTime});
                } else if (actualTime > dist1[nei] && actualTime < dist2[nei]) {
                    dist2[nei] = actualTime;
                    q.offer(new int[]{nei, actualTime});
                }
            }
        }
        return dist2[n];
    }

    public static void main(String[] args) {
        Problem21_SecondMinimumTimeToReachDestination solver = new Problem21_SecondMinimumTimeToReachDestination();
        System.out.println(solver.secondMinimum(5, new int[][]{{1,2},{1,3},{1,4},{3,4},{4,5}}, 3, 5)); // 13
    }
}
