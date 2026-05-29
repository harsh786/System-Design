import java.util.*;

/**
 * Problem 50: Median of Two Sorted Arrays
 * 
 * Find the median of two sorted arrays in O(log(min(m,n))) time.
 * 
 * Approach: Binary search on the smaller array. Find partition where left side has 
 * (m+n+1)/2 elements and max(left) <= min(right).
 * Time Complexity: O(log(min(m,n)))
 * Space Complexity: O(1)
 * 
 * Production Analogy: Computing percentile metrics (P50 latency) across distributed 
 * systems where each node maintains a sorted histogram - merging without full data transfer.
 */
public class Problem50_MedianOfTwoSortedArrays {
    
    public double findMedianSortedArrays(int[] nums1, int[] nums2) {
        // Ensure nums1 is smaller
        if (nums1.length > nums2.length) return findMedianSortedArrays(nums2, nums1);
        
        int m = nums1.length, n = nums2.length;
        int lo = 0, hi = m;
        
        while (lo <= hi) {
            int i = (lo + hi) / 2;        // partition in nums1
            int j = (m + n + 1) / 2 - i;  // partition in nums2
            
            int maxLeft1 = (i == 0) ? Integer.MIN_VALUE : nums1[i - 1];
            int minRight1 = (i == m) ? Integer.MAX_VALUE : nums1[i];
            int maxLeft2 = (j == 0) ? Integer.MIN_VALUE : nums2[j - 1];
            int minRight2 = (j == n) ? Integer.MAX_VALUE : nums2[j];
            
            if (maxLeft1 <= minRight2 && maxLeft2 <= minRight1) {
                // Found correct partition
                int maxLeft = Math.max(maxLeft1, maxLeft2);
                if ((m + n) % 2 == 1) return maxLeft;
                int minRight = Math.min(minRight1, minRight2);
                return (maxLeft + minRight) / 2.0;
            } else if (maxLeft1 > minRight2) {
                hi = i - 1;
            } else {
                lo = i + 1;
            }
        }
        throw new IllegalArgumentException("Input arrays are not sorted");
    }
    
    public static void main(String[] args) {
        Problem50_MedianOfTwoSortedArrays sol = new Problem50_MedianOfTwoSortedArrays();
        
        System.out.println("Test 1: " + sol.findMedianSortedArrays(new int[]{1,3}, new int[]{2})); // 2.0
        System.out.println("Test 2: " + sol.findMedianSortedArrays(new int[]{1,2}, new int[]{3,4})); // 2.5
        System.out.println("Test 3: " + sol.findMedianSortedArrays(new int[]{}, new int[]{1})); // 1.0
        System.out.println("Test 4: " + sol.findMedianSortedArrays(new int[]{2}, new int[]{})); // 2.0
        System.out.println("Test 5: " + sol.findMedianSortedArrays(new int[]{1,3,5,7}, new int[]{2,4,6,8})); // 4.5
        System.out.println("Test 6: " + sol.findMedianSortedArrays(new int[]{100001}, new int[]{100000})); // 100000.5
    }
}
