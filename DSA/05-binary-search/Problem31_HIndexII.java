/**
 * Problem 31: H-Index II
 * 
 * Sorted citations array. Find h-index (h papers with >= h citations).
 * 
 * Approach: Binary search for leftmost index where citations[i] >= n - i.
 * 
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Finding the threshold where at least T services
 * meet an SLA of T ms — a self-referential quality metric.
 */
public class Problem31_HIndexII {
    public static int hIndex(int[] citations) {
        int n = citations.length, lo = 0, hi = n - 1;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            if (citations[mid] >= n - mid) hi = mid - 1;
            else lo = mid + 1;
        }
        return n - lo;
    }

    public static void main(String[] args) {
        System.out.println(hIndex(new int[]{0,1,3,5,6})); // 3
        System.out.println(hIndex(new int[]{1,2,100}));    // 2
        System.out.println(hIndex(new int[]{0}));           // 0
        System.out.println(hIndex(new int[]{100}));         // 1
    }
}
