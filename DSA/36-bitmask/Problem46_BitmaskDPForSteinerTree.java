import java.util.*;

public class Problem46_BitmaskDPForSteinerTree {
    // Minimum cost Steiner tree connecting terminal vertices
    public int steinerTree(int n, int[][] edges, int[] terminals) {
        int t = terminals.length;
        int[][] dist = new int[n][n];
        for (int[] row : dist) Arrays.fill(row, Integer.MAX_VALUE / 2);
        for (int i = 0; i < n; i++) dist[i][i] = 0;
        for (int[] e : edges) { dist[e[0]][e[1]] = e[2]; dist[e[1]][e[0]] = e[2]; }
        // Floyd-Warshall
        for (int k = 0; k < n; k++) for (int i = 0; i < n; i++) for (int j = 0; j < n; j++)
            dist[i][j] = Math.min(dist[i][j], dist[i][k] + dist[k][j]);
        int[][] dp = new int[1 << t][n];
        for (int[] row : dp) Arrays.fill(row, Integer.MAX_VALUE / 2);
        for (int i = 0; i < t; i++) dp[1 << i][terminals[i]] = 0;
        for (int mask = 1; mask < (1 << t); mask++) {
            for (int sub = (mask - 1) & mask; sub > 0; sub = (sub - 1) & mask)
                for (int v = 0; v < n; v++)
                    dp[mask][v] = Math.min(dp[mask][v], dp[sub][v] + dp[mask ^ sub][v]);
            // Dijkstra-like relaxation
            for (int i = 0; i < n; i++) for (int j = 0; j < n; j++)
                dp[mask][j] = Math.min(dp[mask][j], dp[mask][i] + dist[i][j]);
        }
        int ans = Integer.MAX_VALUE;
        for (int v = 0; v < n; v++) ans = Math.min(ans, dp[(1 << t) - 1][v]);
        return ans;
    }

    public static void main(String[] args) {
        int[][] edges = {{0,1,1},{1,2,2},{0,3,3},{3,2,1}};
        System.out.println(new Problem46_BitmaskDPForSteinerTree().steinerTree(4, edges, new int[]{0, 2})); // 3
    }
}
