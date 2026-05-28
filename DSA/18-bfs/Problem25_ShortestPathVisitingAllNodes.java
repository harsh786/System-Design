import java.util.*;

/**
 * Problem: Shortest Path Visiting All Nodes (LeetCode 847)
 * Approach: BFS with bitmask state (node, visited_set) to track visited nodes
 * Time: O(2^N * N^2), Space: O(2^N * N)
 * Production Analogy: Minimum hops to poll all services in a monitoring sweep
 */
public class Problem25_ShortestPathVisitingAllNodes {
    public int shortestPathLength(int[][] graph) {
        int n = graph.length, fullMask = (1 << n) - 1;
        Queue<int[]> q = new LinkedList<>(); // [node, mask]
        Set<String> visited = new HashSet<>();
        for (int i = 0; i < n; i++) {
            int mask = 1 << i;
            q.offer(new int[]{i, mask});
            visited.add(i + "," + mask);
        }
        int steps = 0;
        while (!q.isEmpty()) {
            int size = q.size();
            for (int i = 0; i < size; i++) {
                int[] curr = q.poll();
                if (curr[1] == fullMask) return steps;
                for (int next : graph[curr[0]]) {
                    int newMask = curr[1] | (1 << next);
                    String key = next + "," + newMask;
                    if (!visited.contains(key)) { visited.add(key); q.offer(new int[]{next, newMask}); }
                }
            }
            steps++;
        }
        return -1;
    }

    public static void main(String[] args) {
        int[][] graph = {{1,2,3},{0},{0},{0}};
        System.out.println(new Problem25_ShortestPathVisitingAllNodes().shortestPathLength(graph)); // 4
    }
}
