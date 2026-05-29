import java.util.Arrays;

public class Problem17_TravelingSalesmanDP {
    public int tsp(int[][] dist) {
        int n = dist.length;
        int[][] dp = new int[1 << n][n];
        for (int[] row : dp) Arrays.fill(row, Integer.MAX_VALUE / 2);
        dp[1][0] = 0;
        for (int mask = 1; mask < (1 << n); mask++)
            for (int u = 0; u < n; u++) {
                if ((mask & (1 << u)) == 0 || dp[mask][u] >= Integer.MAX_VALUE / 2) continue;
                for (int v = 0; v < n; v++) {
                    if ((mask & (1 << v)) != 0) continue;
                    dp[mask | (1 << v)][v] = Math.min(dp[mask | (1 << v)][v], dp[mask][u] + dist[u][v]);
                }
            }
        int full = (1 << n) - 1, ans = Integer.MAX_VALUE;
        for (int u = 0; u < n; u++) ans = Math.min(ans, dp[full][u] + dist[u][0]);
        return ans;
    }

    public static void main(String[] args) {
        int[][] dist = {{0,10,15,20},{10,0,35,25},{15,35,0,30},{20,25,30,0}};
        System.out.println(new Problem17_TravelingSalesmanDP().tsp(dist)); // 80
    }
}
