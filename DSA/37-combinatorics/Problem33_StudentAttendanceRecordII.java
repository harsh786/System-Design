public class Problem33_StudentAttendanceRecordII {
    public int checkRecord(int n) {
        long MOD = 1_000_000_007;
        // dp[absent][trailing_late]
        long[][] dp = new long[2][3];
        dp[0][0] = 1;
        for (int i = 0; i < n; i++) {
            long[][] ndp = new long[2][3];
            for (int a = 0; a < 2; a++)
                for (int l = 0; l < 3; l++) {
                    if (dp[a][l] == 0) continue;
                    // Present
                    ndp[a][0] = (ndp[a][0] + dp[a][l]) % MOD;
                    // Late
                    if (l < 2) ndp[a][l+1] = (ndp[a][l+1] + dp[a][l]) % MOD;
                    // Absent
                    if (a == 0) ndp[1][0] = (ndp[1][0] + dp[a][l]) % MOD;
                }
            dp = ndp;
        }
        long result = 0;
        for (int a = 0; a < 2; a++) for (int l = 0; l < 3; l++) result = (result + dp[a][l]) % MOD;
        return (int) result;
    }

    public static void main(String[] args) {
        System.out.println(new Problem33_StudentAttendanceRecordII().checkRecord(10101));
    }
}
