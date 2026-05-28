import java.util.*;

/**
 * Problem 41: Find if Path Exists in Graph (LeetCode 1971)
 * 
 * Approach: BFS/DFS or Union-Find to check connectivity between source and destination.
 * Time: O(V + E), Space: O(V + E)
 * 
 * Production Analogy: Checking if a request can reach a target service through the network.
 */
public class Problem41_FindIfPathExists {
    
    public boolean validPath(int n, int[][] edges, int source, int destination) {
        if (source == destination) return true;
        List<Integer>[] adj = new List[n];
        for (int i = 0; i < n; i++) adj[i] = new ArrayList<>();
        for (int[] e : edges) { adj[e[0]].add(e[1]); adj[e[1]].add(e[0]); }
        boolean[] visited = new boolean[n];
        Queue<Integer> q = new LinkedList<>();
        q.offer(source); visited[source] = true;
        while (!q.isEmpty()) {
            int node = q.poll();
            for (int nei : adj[node]) {
                if (nei == destination) return true;
                if (!visited[nei]) { visited[nei] = true; q.offer(nei); }
            }
        }
        return false;
    }
    
    public static void main(String[] args) {
        Problem41_FindIfPathExists sol = new Problem41_FindIfPathExists();
        System.out.println(sol.validPath(3, new int[][]{{0,1},{1,2},{2,0}}, 0, 2)); // true
        System.out.println(sol.validPath(6, new int[][]{{0,1},{0,2},{3,5},{5,4},{4,3}}, 0, 5)); // false
        System.out.println(sol.validPath(1, new int[][]{}, 0, 0)); // true
    }
}
