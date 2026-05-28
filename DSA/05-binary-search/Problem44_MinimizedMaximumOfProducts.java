/**
 * Problem 44: Minimized Maximum of Products Distributed to Any Store
 * 
 * Distribute products to n stores. Minimize the maximum products any store gets.
 * 
 * Approach: Binary search on answer [1, max(quantities)]. Check if we can
 * distribute with at most 'mid' per store using n stores.
 * 
 * Time: O(m * log(max)), Space: O(1)
 * 
 * Production Analogy: Distributing request quotas across API gateway instances
 * to minimize hotspot load on any single instance.
 */
public class Problem44_MinimizedMaximumOfProducts {
    public static int minimizedMaximum(int n, int[] quantities) {
        int lo = 1, hi = 0;
        for (int q : quantities) hi = Math.max(hi, q);
        
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (canDistribute(quantities, n, mid)) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }

    private static boolean canDistribute(int[] quantities, int n, int maxPerStore) {
        int storesNeeded = 0;
        for (int q : quantities) storesNeeded += (q + maxPerStore - 1) / maxPerStore;
        return storesNeeded <= n;
    }

    public static void main(String[] args) {
        System.out.println(minimizedMaximum(6, new int[]{11,6}));        // 3
        System.out.println(minimizedMaximum(7, new int[]{15,10,10}));    // 5
        System.out.println(minimizedMaximum(1, new int[]{100000}));      // 100000
    }
}
