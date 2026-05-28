import java.util.*;

/**
 * Problem 19: Shortest Path Visiting All Nodes (LeetCode 847)
 * 
 * Approach: BFS with bitmask state (node, visited_set). State = (current_node, bitmask of visited).
 * Time: O(2^N * N^2), Space: O(2^N * N)
 * 
 * Production Analogy: Shortest sequence to health-check all services in a dependency graph.
 */
public class Problem19_ShortestPathVisitingAllNodes {
    
    public int shortestPathLength(int[][] graph) {
        int n = graph.length, fullMask = (1 << n) - 1;
        boolean[][] visited = new boolean[n][1 << n];
        Queue<int[]> q = new LinkedList<>();
        for (int i = 0; i < n; i++) { q.offer(new int[]{i, 1 << i, 0}); visited[i][1 << i] = true; }
        while (!q.isEmpty()) {
            int[] curr = q.poll();
            if (curr[1] == fullMask) return curr[2];
            for (int next : graph[curr[0]]) {
                int newMask = curr[1] | (1 << next);
                if (!visited[next][newMask]) { visited[next][newMask] = true; q.offer(new int[]{next, newMask, curr[2]+1}); }
            }
        }
        return -1;
    }
    
    public static void main(String[] args) {
        Problem19_ShortestPathVisitingAllNodes sol = new Problem19_ShortestPathVisitingAllNodes();
        System.out.println(sol.shortestPathLength(new int[][]{{1,2,3},{0},{0},{0}})); // 4
        System.out.println(sol.shortestPathLength(new int[][]{{1},{0,2,4},{1,3,4},{2},{1,2}})); // 4
    }
}
