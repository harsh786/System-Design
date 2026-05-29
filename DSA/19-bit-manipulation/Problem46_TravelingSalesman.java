/**
 * Problem 46: Traveling Salesman (Bitmask DP)
 * Find minimum cost Hamiltonian path/cycle visiting all cities.
 * 
 * Approach: dp[mask][i] = min cost to visit cities in mask, ending at i.
 * Transition: dp[mask | (1<<j)][j] = min(dp[mask][i] + dist[i][j])
 * Time: O(2^n * n^2), Space: O(2^n * n)
 * 
 * Production Analogy: Optimal routing for delivery/deployment pipelines.
 */
import java.util.*;

public class Problem46_TravelingSalesman {
    public static int tsp(int[][] dist) {
        int n = dist.length;
        int[][] dp = new int[1 << n][n];
        for (int[] row : dp) Arrays.fill(row, Integer.MAX_VALUE / 2);
        dp[1][0] = 0; // start at city 0
        for (int mask = 1; mask < (1 << n); mask++) {
            for (int u = 0; u < n; u++) {
                if ((mask & (1 << u)) == 0 || dp[mask][u] >= Integer.MAX_VALUE / 2) continue;
                for (int v = 0; v < n; v++) {
                    if ((mask & (1 << v)) != 0) continue;
                    int newMask = mask | (1 << v);
                    dp[newMask][v] = Math.min(dp[newMask][v], dp[mask][u] + dist[u][v]);
                }
            }
        }
        int full = (1 << n) - 1, ans = Integer.MAX_VALUE;
        for (int i = 0; i < n; i++)
            ans = Math.min(ans, dp[full][i] + dist[i][0]); // return to start
        return ans;
    }

    public static void main(String[] args) {
        int[][] dist = {{0,10,15,20},{10,0,35,25},{15,35,0,30},{20,25,30,0}};
        System.out.println(tsp(dist)); // 80
    }
}
