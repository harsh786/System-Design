/**
 * Problem 8: Capacity To Ship Packages Within D Days
 * 
 * Find minimum ship capacity to ship all packages in order within d days.
 * 
 * Approach: Binary search on capacity [max(weights), sum(weights)].
 * Monotonic: if capacity c works, c+1 also works.
 * 
 * Time: O(n * log(sum - max)), Space: O(1)
 * 
 * Production Analogy: Determining minimum network bandwidth to transfer
 * all data partitions within a maintenance window.
 */
public class Problem08_CapacityToShipPackages {
    public static int shipWithinDays(int[] weights, int days) {
        int lo = 0, hi = 0;
        for (int w : weights) { lo = Math.max(lo, w); hi += w; }
        
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (canShip(weights, mid, days)) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }

    private static boolean canShip(int[] weights, int cap, int days) {
        int d = 1, load = 0;
        for (int w : weights) {
            if (load + w > cap) { d++; load = 0; }
            load += w;
        }
        return d <= days;
    }

    public static void main(String[] args) {
        System.out.println(shipWithinDays(new int[]{1,2,3,4,5,6,7,8,9,10}, 5)); // 15
        System.out.println(shipWithinDays(new int[]{3,2,2,4,1,4}, 3));           // 6
        System.out.println(shipWithinDays(new int[]{1,2,3,1,1}, 4));             // 3
    }
}
