import java.util.*;

/**
 * Problem 34: Maximal Network Rank (LeetCode 1615)
 * 
 * Approach: For each pair (i,j), rank = degree[i] + degree[j] - (1 if connected). Maximize.
 * Time: O(V^2), Space: O(V + E)
 * 
 * Production Analogy: Finding the pair of routers with maximum combined connectivity (network capacity planning).
 */
public class Problem34_MaximalNetworkRank {
    
    public int maximalNetworkRank(int n, int[][] roads) {
        int[] degree = new int[n];
        Set<Integer>[] adj = new Set[n];
        for (int i = 0; i < n; i++) adj[i] = new HashSet<>();
        for (int[] r : roads) { degree[r[0]]++; degree[r[1]]++; adj[r[0]].add(r[1]); adj[r[1]].add(r[0]); }
        int max = 0;
        for (int i = 0; i < n; i++)
            for (int j = i+1; j < n; j++)
                max = Math.max(max, degree[i] + degree[j] - (adj[i].contains(j) ? 1 : 0));
        return max;
    }
    
    public static void main(String[] args) {
        Problem34_MaximalNetworkRank sol = new Problem34_MaximalNetworkRank();
        System.out.println(sol.maximalNetworkRank(4, new int[][]{{0,1},{0,3},{1,2},{1,3}})); // 4
        System.out.println(sol.maximalNetworkRank(5, new int[][]{{0,1},{0,3},{1,2},{1,3},{2,3},{2,4}})); // 5
        System.out.println(sol.maximalNetworkRank(8, new int[][]{{0,1},{1,2},{2,3},{2,4},{5,6},{5,7}})); // 5
    }
}
