import java.util.*;

/**
 * Problem 38: Detonate the Maximum Bombs (LeetCode 2101)
 * 
 * Approach: Build directed graph (bomb i reaches j if distance <= radius_i). BFS from each, find max reachable.
 * Time: O(N^3), Space: O(N^2)
 * 
 * Production Analogy: Cascading failure analysis - which single service failure causes maximum downstream impact.
 */
public class Problem38_DetonateMaximumBombs {
    
    public int maximumDetonation(int[][] bombs) {
        int n = bombs.length;
        List<Integer>[] adj = new List[n];
        for (int i = 0; i < n; i++) adj[i] = new ArrayList<>();
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++) {
                if (i == j) continue;
                long dx = bombs[i][0]-bombs[j][0], dy = bombs[i][1]-bombs[j][1], r = bombs[i][2];
                if (dx*dx + dy*dy <= r*r) adj[i].add(j);
            }
        int max = 0;
        for (int i = 0; i < n; i++) {
            boolean[] visited = new boolean[n];
            Queue<Integer> q = new LinkedList<>();
            q.offer(i); visited[i] = true; int count = 0;
            while (!q.isEmpty()) { int node = q.poll(); count++;
                for (int next : adj[node]) if (!visited[next]) { visited[next]=true; q.offer(next); } }
            max = Math.max(max, count);
        }
        return max;
    }
    
    public static void main(String[] args) {
        Problem38_DetonateMaximumBombs sol = new Problem38_DetonateMaximumBombs();
        System.out.println(sol.maximumDetonation(new int[][]{{2,1,3},{6,1,4}})); // 2
        System.out.println(sol.maximumDetonation(new int[][]{{1,1,5},{10,10,5}})); // 1
        System.out.println(sol.maximumDetonation(new int[][]{{1,2,3},{2,3,1},{3,4,2},{4,5,3},{5,6,4}})); // 5
    }
}
