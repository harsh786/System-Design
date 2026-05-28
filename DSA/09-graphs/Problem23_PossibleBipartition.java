import java.util.*;

/**
 * Problem 23: Possible Bipartition (LeetCode 886)
 * 
 * Approach: Graph coloring (BFS). Build graph from dislikes, check bipartiteness.
 * Time: O(V + E), Space: O(V + E)
 * 
 * Production Analogy: Splitting conflicting services into two availability zones without conflicts.
 */
public class Problem23_PossibleBipartition {
    
    public boolean possibleBipartition(int n, int[][] dislikes) {
        List<Integer>[] adj = new List[n + 1];
        for (int i = 0; i <= n; i++) adj[i] = new ArrayList<>();
        for (int[] d : dislikes) { adj[d[0]].add(d[1]); adj[d[1]].add(d[0]); }
        int[] color = new int[n + 1];
        for (int i = 1; i <= n; i++) {
            if (color[i] != 0) continue;
            Queue<Integer> q = new LinkedList<>();
            q.offer(i); color[i] = 1;
            while (!q.isEmpty()) {
                int node = q.poll();
                for (int nei : adj[node]) {
                    if (color[nei] == 0) { color[nei] = -color[node]; q.offer(nei); }
                    else if (color[nei] == color[node]) return false;
                }
            }
        }
        return true;
    }
    
    public static void main(String[] args) {
        Problem23_PossibleBipartition sol = new Problem23_PossibleBipartition();
        System.out.println(sol.possibleBipartition(4, new int[][]{{1,2},{1,3},{2,4}})); // true
        System.out.println(sol.possibleBipartition(3, new int[][]{{1,2},{1,3},{2,3}})); // false
        System.out.println(sol.possibleBipartition(5, new int[][]{{1,2},{2,3},{3,4},{4,5},{1,5}})); // false
    }
}
