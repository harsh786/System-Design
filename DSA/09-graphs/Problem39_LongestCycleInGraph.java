import java.util.*;

/**
 * Problem 39: Longest Cycle in a Graph (LeetCode 2360)
 * 
 * Approach: Each node has at most 1 outgoing edge. Track visit time per DFS, detect cycle length.
 * Time: O(N), Space: O(N)
 * 
 * Production Analogy: Finding the longest circular dependency chain in a task scheduler.
 */
public class Problem39_LongestCycleInGraph {
    
    public int longestCycle(int[] edges) {
        int n = edges.length, ans = -1;
        int[] visited = new int[n];
        Arrays.fill(visited, -1);
        int time = 0;
        for (int i = 0; i < n; i++) {
            if (visited[i] != -1) continue;
            int start = time, node = i;
            while (node != -1 && visited[node] == -1) {
                visited[node] = time++;
                node = edges[node];
            }
            if (node != -1 && visited[node] >= start)
                ans = Math.max(ans, time - visited[node]);
        }
        return ans;
    }
    
    public static void main(String[] args) {
        Problem39_LongestCycleInGraph sol = new Problem39_LongestCycleInGraph();
        System.out.println(sol.longestCycle(new int[]{3,3,4,2,3})); // 3
        System.out.println(sol.longestCycle(new int[]{2,-1,3,1})); // -1
        System.out.println(sol.longestCycle(new int[]{1,2,0})); // 3
    }
}
