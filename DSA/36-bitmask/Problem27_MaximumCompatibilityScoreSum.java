import java.util.Arrays;

public class Problem27_MaximumCompatibilityScoreSum {
    public int maxCompatibilitySum(int[][] students, int[][] mentors) {
        int m = students.length, n = students[0].length;
        int[][] score = new int[m][m];
        for (int i = 0; i < m; i++) for (int j = 0; j < m; j++)
            for (int k = 0; k < n; k++) if (students[i][k] == mentors[j][k]) score[i][j]++;
        int[] dp = new int[1 << m];
        for (int mask = 0; mask < (1 << m); mask++) {
            int student = Integer.bitCount(mask);
            if (student >= m) continue;
            for (int j = 0; j < m; j++) {
                if ((mask & (1 << j)) != 0) continue;
                dp[mask | (1 << j)] = Math.max(dp[mask | (1 << j)], dp[mask] + score[student][j]);
            }
        }
        return dp[(1 << m) - 1];
    }

    public static void main(String[] args) {
        System.out.println(new Problem27_MaximumCompatibilityScoreSum().maxCompatibilitySum(
            new int[][]{{1,1,0},{1,0,1},{0,0,1}}, new int[][]{{1,0,0},{0,0,1},{1,1,0}}));
    }
}
