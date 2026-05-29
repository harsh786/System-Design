import java.util.*;

/**
 * Problem: Shortest Path Visiting All Nodes
 * Find shortest path that visits all nodes in an undirected graph.
 *
 * Approach: BFS with bitmask state (node, visited_mask)
 *
 * Time Complexity: O(2^N * N^2)
 * Space Complexity: O(2^N * N)
 *
 * Production Analogy: Minimum steps to health-check all services in a network.
 */
public class Problem13_ShortestPathVisitingAllNodes {

    public int shortestPathLength(int[][] graph) {
        int n = graph.length, target = (1 << n) - 1;
        Queue<int[]> q = new LinkedList<>();
        boolean[][] visited = new boolean[n][1 << n];

        for (int i = 0; i < n; i++) {
            q.offer(new int[]{i, 1 << i, 0});
            visited[i][1 << i] = true;
        }

        while (!q.isEmpty()) {
            int[] cur = q.poll();
            if (cur[1] == target) return cur[2];
            for (int nei : graph[cur[0]]) {
                int mask = cur[1] | (1 << nei);
                if (!visited[nei][mask]) {
                    visited[nei][mask] = true;
                    q.offer(new int[]{nei, mask, cur[2] + 1});
                }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem13_ShortestPathVisitingAllNodes solver = new Problem13_ShortestPathVisitingAllNodes();
        System.out.println(solver.shortestPathLength(new int[][]{{1,2,3},{0},{0},{0}})); // 4
    }
}
