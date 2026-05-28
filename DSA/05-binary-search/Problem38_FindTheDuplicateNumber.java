/**
 * Problem 38: Find the Duplicate Number
 * 
 * Array of n+1 integers in [1,n]. One duplicate exists. Find it.
 * 
 * Approach: Binary search on value space [1,n]. For mid, count numbers <= mid.
 * If count > mid, duplicate is in [lo, mid]. (Pigeonhole principle)
 * 
 * Time: O(n log n), Space: O(1)
 * 
 * Production Analogy: Detecting a duplicate key in a sharded system by counting
 * keys per range — like checking partition key distribution for hotspots.
 */
public class Problem38_FindTheDuplicateNumber {
    public static int findDuplicate(int[] nums) {
        int lo = 1, hi = nums.length - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            int count = 0;
            for (int n : nums) if (n <= mid) count++;
            if (count > mid) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }

    public static void main(String[] args) {
        System.out.println(findDuplicate(new int[]{1,3,4,2,2}));   // 2
        System.out.println(findDuplicate(new int[]{3,1,3,4,2}));   // 3
        System.out.println(findDuplicate(new int[]{1,1}));          // 1
        System.out.println(findDuplicate(new int[]{2,2,2,2,2}));   // 2
    }
}
