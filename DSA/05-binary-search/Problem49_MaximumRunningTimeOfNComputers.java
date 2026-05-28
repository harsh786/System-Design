/**
 * Problem 49: Maximum Running Time of N Computers
 * 
 * n computers, batteries with charges. Each battery powers one computer at a time.
 * Find maximum minutes all n computers can run simultaneously.
 * 
 * Approach: Binary search on time [0, sum/n]. Check if total energy >= n * mid.
 * Each battery contributes min(charge, mid) to the pool.
 * 
 * Time: O(m * log(sum/n)), Space: O(1)
 * 
 * Production Analogy: Maximum time n services can run given distributed power
 * budgets (CPU credits) with sharing constraints.
 */
public class Problem49_MaximumRunningTimeOfNComputers {
    public static long maxRunTime(int n, int[] batteries) {
        long lo = 0, hi = 0;
        for (int b : batteries) hi += b;
        hi /= n;
        
        while (lo < hi) {
            long mid = lo + (hi - lo + 1) / 2;
            if (canRun(batteries, n, mid)) lo = mid;
            else hi = mid - 1;
        }
        return lo;
    }

    private static boolean canRun(int[] batteries, int n, long time) {
        long total = 0;
        for (int b : batteries) total += Math.min(b, time);
        return total >= (long) n * time;
    }

    public static void main(String[] args) {
        System.out.println(maxRunTime(2, new int[]{3,3,3}));      // 4
        System.out.println(maxRunTime(2, new int[]{1,1,1,1}));    // 2
        System.out.println(maxRunTime(3, new int[]{10,10,3,5}));  // 8
    }
}
