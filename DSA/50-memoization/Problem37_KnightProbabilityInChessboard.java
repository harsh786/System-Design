import java.util.*;

public class Problem37_KnightProbabilityInChessboard {
    private Double[][][] memo;
    private static final int[][] dirs = {{-2,-1},{-2,1},{-1,-2},{-1,2},{1,-2},{1,2},{2,-1},{2,1}};

    public double knightProbability(int n, int k, int row, int column) {
        memo = new Double[n][n][k + 1];
        return helper(n, k, row, column);
    }

    private double helper(int n, int k, int r, int c) {
        if (r < 0 || r >= n || c < 0 || c >= n) return 0;
        if (k == 0) return 1;
        if (memo[r][c][k] != null) return memo[r][c][k];
        double prob = 0;
        for (int[] d : dirs) prob += helper(n, k - 1, r + d[0], c + d[1]) / 8.0;
        memo[r][c][k] = prob;
        return prob;
    }

    public static void main(String[] args) {
        Problem37_KnightProbabilityInChessboard sol = new Problem37_KnightProbabilityInChessboard();
        System.out.printf("Probability: %.5f%n", sol.knightProbability(3, 2, 0, 0)); // 0.0625
    }
}
