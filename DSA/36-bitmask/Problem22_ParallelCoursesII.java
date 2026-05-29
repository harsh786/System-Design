import java.util.Arrays;

public class Problem22_ParallelCoursesII {
    public int minNumberOfSemesters(int n, int[][] relations, int k) {
        int[] prereq = new int[n];
        for (int[] r : relations) prereq[r[1]-1] |= (1 << (r[0]-1));
        int[] dp = new int[1 << n];
        Arrays.fill(dp, n);
        dp[0] = 0;
        for (int mask = 0; mask < (1 << n); mask++) {
            if (dp[mask] == n) continue;
            int canTake = 0;
            for (int i = 0; i < n; i++) if ((mask & (1 << i)) == 0 && (prereq[i] & mask) == prereq[i]) canTake |= (1 << i);
            for (int sub = canTake; sub > 0; sub = (sub - 1) & canTake) {
                if (Integer.bitCount(sub) <= k) dp[mask | sub] = Math.min(dp[mask | sub], dp[mask] + 1);
            }
        }
        return dp[(1 << n) - 1];
    }

    public static void main(String[] args) {
        System.out.println(new Problem22_ParallelCoursesII().minNumberOfSemesters(4, new int[][]{{2,1},{3,1},{1,4}}, 2));
    }
}
