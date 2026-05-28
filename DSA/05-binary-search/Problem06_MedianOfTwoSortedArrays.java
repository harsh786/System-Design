/**
 * Problem 6: Median of Two Sorted Arrays
 * 
 * Find the median of two sorted arrays in O(log(min(m,n))) time.
 * 
 * Approach: Binary search on the shorter array to find correct partition.
 * Invariant: Partition divides combined arrays into two equal halves where
 * all elements in left half <= all elements in right half.
 * 
 * Time: O(log(min(m,n))), Space: O(1)
 * 
 * Production Analogy: Merging two sorted shards of a distributed database
 * to find the median latency without materializing the full merge.
 */
public class Problem06_MedianOfTwoSortedArrays {
    public static double findMedianSortedArrays(int[] nums1, int[] nums2) {
        // Ensure nums1 is the shorter array
        if (nums1.length > nums2.length) return findMedianSortedArrays(nums2, nums1);
        
        int m = nums1.length, n = nums2.length;
        int lo = 0, hi = m;
        
        while (lo <= hi) {
            int i = lo + (hi - lo) / 2;  // partition in nums1
            int j = (m + n + 1) / 2 - i; // partition in nums2
            
            int maxLeft1 = (i == 0) ? Integer.MIN_VALUE : nums1[i - 1];
            int minRight1 = (i == m) ? Integer.MAX_VALUE : nums1[i];
            int maxLeft2 = (j == 0) ? Integer.MIN_VALUE : nums2[j - 1];
            int minRight2 = (j == n) ? Integer.MAX_VALUE : nums2[j];
            
            if (maxLeft1 <= minRight2 && maxLeft2 <= minRight1) {
                if ((m + n) % 2 == 0)
                    return (Math.max(maxLeft1, maxLeft2) + Math.min(minRight1, minRight2)) / 2.0;
                else
                    return Math.max(maxLeft1, maxLeft2);
            } else if (maxLeft1 > minRight2) {
                hi = i - 1;
            } else {
                lo = i + 1;
            }
        }
        throw new IllegalArgumentException("Input arrays are not sorted");
    }

    public static void main(String[] args) {
        System.out.println(findMedianSortedArrays(new int[]{1,3}, new int[]{2}));       // 2.0
        System.out.println(findMedianSortedArrays(new int[]{1,2}, new int[]{3,4}));     // 2.5
        System.out.println(findMedianSortedArrays(new int[]{}, new int[]{1}));          // 1.0
        System.out.println(findMedianSortedArrays(new int[]{2}, new int[]{}));          // 2.0
        System.out.println(findMedianSortedArrays(new int[]{1,3,5}, new int[]{2,4,6}));// 3.5
    }
}
