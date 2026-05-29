import java.util.Arrays;

public class Problem44_BitmaskDPForCliqueCover {
    // Minimum clique cover: partition vertices into minimum number of cliques
    public int minCliqueCover(int[][] adj) {
        int n = adj.length;
        boolean[] isClique = new boolean[1 << n];
        isClique[0] = true;
        for (int mask = 1; mask < (1 << n); mask++) {
            int lsb = Integer.numberOfTrailingZeros(mask);
            int rest = mask ^ (1 << lsb);
            isClique[mask] = isClique[rest];
            if (isClique[mask])
                for (int i = 0; i < n; i++)
                    if (i != lsb && (mask & (1 << i)) != 0 && adj[lsb][i] == 0) { isClique[mask] = false; break; }
        }
        int full = (1 << n) - 1;
        int[] dp = new int[1 << n];
        Arrays.fill(dp, n);
        dp[0] = 0;
        for (int mask = 1; mask <= full; mask++)
            for (int sub = mask; sub > 0; sub = (sub - 1) & mask)
                if (isClique[sub]) dp[mask] = Math.min(dp[mask], dp[mask ^ sub] + 1);
        return dp[full];
    }

    public static void main(String[] args) {
        int[][] adj = {{0,1,0,0},{1,0,1,0},{0,1,0,1},{0,0,1,0}};
        System.out.println(new Problem44_BitmaskDPForCliqueCover().minCliqueCover(adj));
    }
}
