import java.util.Arrays;

public class Problem23_MaximumStudentsTakingExam {
    public int maxStudents(char[][] seats) {
        int m = seats.length, n = seats[0].length;
        int[] valid = new int[m];
        for (int i = 0; i < m; i++) for (int j = 0; j < n; j++) if (seats[i][j] == '.') valid[i] |= (1 << j);
        int[][] dp = new int[m + 1][1 << n];
        for (int[] row : dp) Arrays.fill(row, -1);
        dp[0][0] = 0;
        int ans = 0;
        for (int i = 1; i <= m; i++)
            for (int mask = 0; mask < (1 << n); mask++) {
                if ((mask & valid[i-1]) != mask) continue;
                if ((mask & (mask << 1)) != 0) continue;
                for (int prev = 0; prev < (1 << n); prev++) {
                    if (dp[i-1][prev] == -1) continue;
                    if ((mask & (prev << 1)) != 0 || (mask & (prev >> 1)) != 0) continue;
                    dp[i][mask] = Math.max(dp[i][mask], dp[i-1][prev] + Integer.bitCount(mask));
                    ans = Math.max(ans, dp[i][mask]);
                }
            }
        return ans;
    }

    public static void main(String[] args) {
        System.out.println(new Problem23_MaximumStudentsTakingExam().maxStudents(new char[][]{{'#','.','#','#','.','#'},{'.','#','#','#','#','.'},{'#','.','#','#','.','#'}}));
    }
}
