/**
 * Problem 21: Allocate Minimum Pages
 * 
 * Allocate n books to k students (contiguous). Minimize max pages any student reads.
 * 
 * Approach: Binary search on [max(pages), sum(pages)]. Same pattern as split array.
 * 
 * Time: O(n * log(sum - max)), Space: O(1)
 * 
 * Production Analogy: Distributing contiguous log partitions across k consumers
 * to minimize maximum consumer lag.
 */
public class Problem21_AllocateMinimumPages {
    public static int allocatePages(int[] pages, int k) {
        if (k > pages.length) return -1;
        int lo = 0, hi = 0;
        for (int p : pages) { lo = Math.max(lo, p); hi += p; }
        
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (canAllocate(pages, mid, k)) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }

    private static boolean canAllocate(int[] pages, int maxPages, int k) {
        int students = 1, cur = 0;
        for (int p : pages) {
            if (cur + p > maxPages) { students++; cur = 0; }
            cur += p;
        }
        return students <= k;
    }

    public static void main(String[] args) {
        System.out.println(allocatePages(new int[]{12,34,67,90}, 2)); // 113
        System.out.println(allocatePages(new int[]{10,20,30,40}, 2)); // 60
        System.out.println(allocatePages(new int[]{5,10,30,20,15}, 3)); // 30
    }
}
