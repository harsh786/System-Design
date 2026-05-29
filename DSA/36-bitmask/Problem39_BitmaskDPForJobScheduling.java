import java.util.Arrays;

public class Problem39_BitmaskDPForJobScheduling {
    // Schedule jobs on machines minimizing makespan, each job assigned to exactly one machine
    public int minMakespan(int[] jobs, int k) {
        int n = jobs.length;
        int[] subSum = new int[1 << n];
        for (int mask = 1; mask < (1 << n); mask++) {
            int lsb = Integer.numberOfTrailingZeros(mask);
            subSum[mask] = subSum[mask ^ (1 << lsb)] + jobs[lsb];
        }
        int[] dp = new int[1 << n];
        Arrays.fill(dp, Integer.MAX_VALUE);
        dp[0] = 0;
        // Greedy bitmask approach: partition into k groups minimizing max group sum
        int[][] dpk = new int[k + 1][1 << n];
        for (int[] row : dpk) Arrays.fill(row, Integer.MAX_VALUE);
        dpk[0][0] = 0;
        for (int i = 1; i <= k; i++)
            for (int mask = 0; mask < (1 << n); mask++) {
                for (int sub = mask; sub > 0; sub = (sub - 1) & mask)
                    if (dpk[i-1][mask ^ sub] != Integer.MAX_VALUE)
                        dpk[i][mask] = Math.min(dpk[i][mask], Math.max(dpk[i-1][mask ^ sub], subSum[sub]));
                if (mask == 0) dpk[i][0] = 0;
            }
        return dpk[k][(1 << n) - 1];
    }

    public static void main(String[] args) {
        System.out.println(new Problem39_BitmaskDPForJobScheduling().minMakespan(new int[]{1,2,4,7,8}, 2));
    }
}
