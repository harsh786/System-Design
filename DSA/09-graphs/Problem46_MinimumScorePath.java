import java.util.*;

/**
 * Problem 46: Minimum Score of a Path Between Two Cities (LeetCode 2492)
 * 
 * Approach: BFS/DFS from node 1. Find minimum edge weight in the connected component containing 1 and n.
 * Time: O(V + E), Space: O(V + E)
 * 
 * Production Analogy: Finding the weakest link (bottleneck bandwidth) in the reachable network from source to dest.
 */
public class Problem46_MinimumScorePath {
    
    public int minScore(int n, int[][] roads) {
        List<int[]>[] adj = new List[n + 1];
        for (int i = 0; i <= n; i++) adj[i] = new ArrayList<>();
        for (int[] r : roads) { adj[r[0]].add(new int[]{r[1],r[2]}); adj[r[1]].add(new int[]{r[0],r[2]}); }
        boolean[] visited = new boolean[n + 1];
        Queue<Integer> q = new LinkedList<>();
        q.offer(1); visited[1] = true;
        int min = Integer.MAX_VALUE;
        while (!q.isEmpty()) {
            int node = q.poll();
            for (int[] nei : adj[node]) {
                min = Math.min(min, nei[1]);
                if (!visited[nei[0]]) { visited[nei[0]] = true; q.offer(nei[0]); }
            }
        }
        return min;
    }
    
    public static void main(String[] args) {
        Problem46_MinimumScorePath sol = new Problem46_MinimumScorePath();
        System.out.println(sol.minScore(4, new int[][]{{1,2,9},{2,3,6},{2,4,5},{1,4,7}})); // 5
        System.out.println(sol.minScore(4, new int[][]{{1,2,2},{1,3,4},{3,4,7}})); // 2
    }
}
