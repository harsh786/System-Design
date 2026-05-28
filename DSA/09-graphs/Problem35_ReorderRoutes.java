import java.util.*;

/**
 * Problem 35: Reorder Routes to Make All Paths Lead to City Zero (LeetCode 1466)
 * 
 * Approach: BFS from city 0. For each edge away from 0 in the BFS tree, it needs reversal.
 * Time: O(V + E), Space: O(V + E)
 * 
 * Production Analogy: Reorienting one-way network links so all traffic can reach the central gateway.
 */
public class Problem35_ReorderRoutes {
    
    public int minReorder(int n, int[][] connections) {
        List<int[]>[] adj = new List[n]; // [neighbor, direction: 1=original, 0=reverse]
        for (int i = 0; i < n; i++) adj[i] = new ArrayList<>();
        for (int[] c : connections) { adj[c[0]].add(new int[]{c[1], 1}); adj[c[1]].add(new int[]{c[0], 0}); }
        boolean[] visited = new boolean[n];
        Queue<Integer> q = new LinkedList<>();
        q.offer(0); visited[0] = true;
        int count = 0;
        while (!q.isEmpty()) {
            int node = q.poll();
            for (int[] nei : adj[node]) {
                if (!visited[nei[0]]) { visited[nei[0]] = true; count += nei[1]; q.offer(nei[0]); }
            }
        }
        return count;
    }
    
    public static void main(String[] args) {
        Problem35_ReorderRoutes sol = new Problem35_ReorderRoutes();
        System.out.println(sol.minReorder(6, new int[][]{{0,1},{1,3},{2,3},{4,0},{4,5}})); // 3
        System.out.println(sol.minReorder(5, new int[][]{{1,0},{1,2},{3,2},{3,4}})); // 2
        System.out.println(sol.minReorder(3, new int[][]{{1,0},{2,0}})); // 0
    }
}
