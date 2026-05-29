import java.util.*;

public class Problem09_KnightProbability {
    public double knightProbability(int n, int k, int row, int col) {
        int[][] dirs = {{-2,-1},{-2,1},{-1,-2},{-1,2},{1,-2},{1,2},{2,-1},{2,1}};
        double[][] dp = new double[n][n];
        dp[row][col] = 1.0;
        for (int step = 0; step < k; step++) {
            double[][] next = new double[n][n];
            for (int r = 0; r < n; r++) for (int c = 0; c < n; c++) {
                if (dp[r][c] > 0) for (int[] d : dirs) {
                    int nr = r+d[0], nc = c+d[1];
                    if (nr >= 0 && nr < n && nc >= 0 && nc < n) next[nr][nc] += dp[r][c] / 8.0;
                }
            }
            dp = next;
        }
        double prob = 0;
        for (double[] r : dp) for (double v : r) prob += v;
        return prob;
    }

    public static void main(String[] args) {
        Problem09_KnightProbability sol = new Problem09_KnightProbability();
        System.out.println(sol.knightProbability(3, 2, 0, 0));
    }
}
