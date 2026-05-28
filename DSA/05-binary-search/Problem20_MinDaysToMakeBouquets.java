/**
 * Problem 20: Minimum Number of Days to Make m Bouquets
 * 
 * Each flower blooms on bloomDay[i]. Need m bouquets of k adjacent flowers.
 * Find minimum days to wait.
 * 
 * Approach: Binary search on days [min, max]. Check feasibility greedily.
 * 
 * Time: O(n * log(max - min)), Space: O(1)
 * 
 * Production Analogy: Determining minimum wait time before enough adjacent
 * servers in a rack are provisioned to form a replication group.
 */
public class Problem20_MinDaysToMakeBouquets {
    public static int minDays(int[] bloomDay, int m, int k) {
        if ((long) m * k > bloomDay.length) return -1;
        int lo = Integer.MAX_VALUE, hi = Integer.MIN_VALUE;
        for (int d : bloomDay) { lo = Math.min(lo, d); hi = Math.max(hi, d); }
        
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (canMake(bloomDay, mid, m, k)) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }

    private static boolean canMake(int[] bloomDay, int day, int m, int k) {
        int bouquets = 0, flowers = 0;
        for (int d : bloomDay) {
            if (d <= day) { flowers++; if (flowers == k) { bouquets++; flowers = 0; } }
            else flowers = 0;
        }
        return bouquets >= m;
    }

    public static void main(String[] args) {
        System.out.println(minDays(new int[]{1,10,3,10,2}, 3, 1));    // 3
        System.out.println(minDays(new int[]{1,10,3,10,2}, 3, 2));    // -1
        System.out.println(minDays(new int[]{7,7,7,7,12,7,7}, 2, 3)); // 12
    }
}
