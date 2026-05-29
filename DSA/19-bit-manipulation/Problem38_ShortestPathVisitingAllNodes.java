/**
 * Problem 38: Shortest Path Visiting All Nodes
 * Find shortest path that visits every node in an undirected graph.
 * 
 * Approach: BFS with state (current_node, visited_mask). Start from all nodes simultaneously.
 * Time: O(2^n * n^2), Space: O(2^n * n)
 * 
 * Production Analogy: Minimum hops to propagate updates to all nodes in a mesh network.
 */
import java.util.*;

public class Problem38_ShortestPathVisitingAllNodes {
    public static int shortestPathLength(int[][] graph) {
        int n = graph.length;
        int target = (1 << n) - 1;
        boolean[][] visited = new boolean[n][1 << n];
        Queue<int[]> queue = new LinkedList<>();
        for (int i = 0; i < n; i++) {
            queue.offer(new int[]{i, 1 << i, 0});
            visited[i][1 << i] = true;
        }
        while (!queue.isEmpty()) {
            int[] curr = queue.poll();
            int node = curr[0], mask = curr[1], dist = curr[2];
            if (mask == target) return dist;
            for (int next : graph[node]) {
                int newMask = mask | (1 << next);
                if (!visited[next][newMask]) {
                    visited[next][newMask] = true;
                    queue.offer(new int[]{next, newMask, dist + 1});
                }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println(shortestPathLength(new int[][]{{1,2,3},{0},{0},{0}})); // 4
        System.out.println(shortestPathLength(new int[][]{{1},{0,2,4},{1,3,4},{2},{1,2}})); // 4
    }
}
