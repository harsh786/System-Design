import java.util.Arrays;

public class Problem35_BitmaskHamiltonianPath {
    public boolean hasHamiltonianPath(int[][] graph) {
        int n = graph.length;
        boolean[][] dp = new boolean[1 << n][n];
        for (int i = 0; i < n; i++) dp[1 << i][i] = true;
        for (int mask = 0; mask < (1 << n); mask++)
            for (int u = 0; u < n; u++) {
                if (!dp[mask][u]) continue;
                for (int v = 0; v < n; v++)
                    if ((mask & (1 << v)) == 0 && graph[u][v] == 1)
                        dp[mask | (1 << v)][v] = true;
            }
        int full = (1 << n) - 1;
        for (int i = 0; i < n; i++) if (dp[full][i]) return true;
        return false;
    }

    public static void main(String[] args) {
        int[][] g = {{0,1,1,0},{1,0,1,1},{1,1,0,1},{0,1,1,0}};
        System.out.println(new Problem35_BitmaskHamiltonianPath().hasHamiltonianPath(g));
    }
}
