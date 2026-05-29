/**
 * Problem 30: Kth Element of Two Sorted Arrays
 * 
 * D&C Approach:
 * - DIVIDE: Compare k/2-th elements of both arrays
 * - CONQUER: If a[k/2] < b[k/2], first k/2 elements of a can be discarded
 *   (they can't contain the kth element). Recurse with reduced k.
 * - Base cases: one array exhausted, or k=1
 * 
 * Time: O(log k), Space: O(log k) recursion
 * 
 * Production Analogy:
 * - Finding percentiles across sorted partitions without full merge
 * - Distributed ORDER BY with OFFSET/LIMIT optimization
 */
public class Problem30_KthElementOfTwoSortedArrays {

    public static int kthElement(int[] a, int[] b, int k) {
        return kth(a, 0, b, 0, k);
    }

    private static int kth(int[] a, int aStart, int[] b, int bStart, int k) {
        if (aStart >= a.length) return b[bStart + k - 1];
        if (bStart >= b.length) return a[aStart + k - 1];
        if (k == 1) return Math.min(a[aStart], b[bStart]);
        
        int half = k / 2;
        int aVal = (aStart + half - 1 < a.length) ? a[aStart + half - 1] : Integer.MAX_VALUE;
        int bVal = (bStart + half - 1 < b.length) ? b[bStart + half - 1] : Integer.MAX_VALUE;
        
        if (aVal < bVal) return kth(a, aStart + half, b, bStart, k - half);
        else return kth(a, aStart, b, bStart + half, k - half);
    }

    public static void main(String[] args) {
        System.out.println(kthElement(new int[]{2,3,6,7,9}, new int[]{1,4,8,10}, 5)); // 6
        System.out.println(kthElement(new int[]{1,2}, new int[]{3,4}, 3)); // 3
        System.out.println(kthElement(new int[]{1}, new int[]{2}, 1)); // 1
        System.out.println(kthElement(new int[]{1}, new int[]{2}, 2)); // 2
        System.out.println(kthElement(new int[]{}, new int[]{1,2,3}, 2)); // 2
    }
}
