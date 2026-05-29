import java.util.*;

public class Problem28_JobSchedulingNonOverlapping {
    public int jobScheduling(int[] start, int[] end, int[] profit) {
        int n = start.length;
        int[][] jobs = new int[n][3];
        for (int i = 0; i < n; i++) jobs[i] = new int[]{start[i], end[i], profit[i]};
        Arrays.sort(jobs, (a, b) -> a[1] - b[1]);
        int[] dp = new int[n + 1];
        for (int i = 1; i <= n; i++) {
            int lo = 0, hi = i - 1;
            while (lo < hi) { int mid = (lo + hi + 1) / 2; if (jobs[mid - 1][1] <= jobs[i - 1][0]) lo = mid; else hi = mid - 1; }
            dp[i] = Math.max(dp[i - 1], dp[lo] + jobs[i - 1][2]);
        }
        return dp[n];
    }

    public static void main(String[] args) {
        Problem28_JobSchedulingNonOverlapping sol = new Problem28_JobSchedulingNonOverlapping();
        System.out.println(sol.jobScheduling(new int[]{1,2,3,3}, new int[]{3,4,5,6}, new int[]{50,10,40,70})); // 120
    }
}
