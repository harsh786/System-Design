/**
 * Problem 4: Median of Two Sorted Arrays (LeetCode 4)
 * 
 * D&C Approach:
 * - DIVIDE: Binary search on the smaller array to find correct partition
 * - The partition divides both arrays such that left elements <= right elements
 * - No explicit CONQUER/COMBINE - binary search narrows the partition point
 * 
 * Time: O(log(min(m,n))), Space: O(1)
 * 
 * Production Analogy:
 * - Merging sorted shards in distributed databases to find percentiles
 * - Finding median response time across multiple server logs without full merge
 */
public class Problem04_MedianOfTwoSortedArrays {

    public static double findMedianSortedArrays(int[] nums1, int[] nums2) {
        // Always binary search on smaller array
        if (nums1.length > nums2.length) return findMedianSortedArrays(nums2, nums1);
        
        int m = nums1.length, n = nums2.length;
        int lo = 0, hi = m;
        
        while (lo <= hi) {
            int i = (lo + hi) / 2;       // Partition in nums1
            int j = (m + n + 1) / 2 - i; // Partition in nums2
            
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
        System.out.println(findMedianSortedArrays(new int[]{1,3}, new int[]{2})); // 2.0
        System.out.println(findMedianSortedArrays(new int[]{1,2}, new int[]{3,4})); // 2.5
        System.out.println(findMedianSortedArrays(new int[]{}, new int[]{1})); // 1.0
        System.out.println(findMedianSortedArrays(new int[]{2}, new int[]{})); // 2.0
        System.out.println(findMedianSortedArrays(new int[]{1,3,5,7}, new int[]{2,4,6,8})); // 4.5
    }
}
