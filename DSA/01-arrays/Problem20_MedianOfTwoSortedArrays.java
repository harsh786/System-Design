/**
 * Problem 20: Median of Two Sorted Arrays
 * Find median of two sorted arrays in O(log(min(m,n))).
 * 
 * Production Analogy: Like merging two sorted event streams and finding the
 * percentile boundary without fully merging - critical for real-time analytics.
 * 
 * O(log(min(m,n))) time, O(1) space - binary search on smaller array
 */
public class Problem20_MedianOfTwoSortedArrays {

    public static double findMedianSortedArrays(int[] nums1, int[] nums2) {
        if (nums1.length > nums2.length) return findMedianSortedArrays(nums2, nums1);
        int m = nums1.length, n = nums2.length;
        int lo = 0, hi = m;
        while (lo <= hi) {
            int i = (lo + hi) / 2;
            int j = (m + n + 1) / 2 - i;
            int maxLeft1 = (i == 0) ? Integer.MIN_VALUE : nums1[i-1];
            int minRight1 = (i == m) ? Integer.MAX_VALUE : nums1[i];
            int maxLeft2 = (j == 0) ? Integer.MIN_VALUE : nums2[j-1];
            int minRight2 = (j == n) ? Integer.MAX_VALUE : nums2[j];
            if (maxLeft1 <= minRight2 && maxLeft2 <= minRight1) {
                if ((m + n) % 2 == 0)
                    return (Math.max(maxLeft1, maxLeft2) + Math.min(minRight1, minRight2)) / 2.0;
                else
                    return Math.max(maxLeft1, maxLeft2);
            } else if (maxLeft1 > minRight2) hi = i - 1;
            else lo = i + 1;
        }
        return 0;
    }

    public static void main(String[] args) {
        System.out.println(findMedianSortedArrays(new int[]{1,3}, new int[]{2}));    // 2.0
        System.out.println(findMedianSortedArrays(new int[]{1,2}, new int[]{3,4}));  // 2.5
        System.out.println(findMedianSortedArrays(new int[]{}, new int[]{1}));       // 1.0
    }
}
