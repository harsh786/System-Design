import java.util.*;

public class Problem29_WeightedJobScheduling {
    public int weightedJobScheduling(int[][] jobs) {
        // jobs: [start, end, weight]
        Arrays.sort(jobs, (a, b) -> a[1] - b[1]);
        int n = jobs.length;
        int[] dp = new int[n];
        dp[0] = jobs[0][2];
        for (int i = 1; i < n; i++) {
            int incl = jobs[i][2];
            int lo = 0, hi = i - 1, last = -1;
            while (lo <= hi) { int mid = (lo + hi) / 2; if (jobs[mid][1] <= jobs[i][0]) { last = mid; lo = mid + 1; } else hi = mid - 1; }
            if (last != -1) incl += dp[last];
            dp[i] = Math.max(dp[i - 1], incl);
        }
        return dp[n - 1];
    }

    public static void main(String[] args) {
        Problem29_WeightedJobScheduling sol = new Problem29_WeightedJobScheduling();
        System.out.println(sol.weightedJobScheduling(new int[][]{{1,3,50},{2,4,10},{3,5,40},{3,6,70}})); // 120
    }
}
