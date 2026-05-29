import java.util.*;

/**
 * Problem 6: Maximum Gap (LeetCode 164)
 * 
 * Given an integer array, return the maximum difference between two successive
 * elements in its sorted form. Must run in O(n) time and O(n) space.
 * 
 * Approach 1: Radix Sort then scan - O(d*n) time
 * Approach 2: Bucket/Pigeonhole approach - O(n) time
 * 
 * Bucket insight: Maximum gap >= ceil((max-min)/(n-1)) by pigeonhole.
 * Create buckets of this size. Max gap must be between buckets, not within.
 */
public class Problem06_MaximumGap {

    // Approach 1: Radix Sort
    public static int maximumGapRadix(int[] nums) {
        if (nums.length < 2) return 0;
        
        // Radix sort
        int max = 0;
        for (int v : nums) max = Math.max(max, v);
        
        int[] output = new int[nums.length];
        for (int exp = 1; max / exp > 0; exp *= 10) {
            int[] count = new int[10];
            for (int v : nums) count[(v/exp)%10]++;
            for (int i = 1; i < 10; i++) count[i] += count[i-1];
            for (int i = nums.length-1; i >= 0; i--) {
                output[--count[(nums[i]/exp)%10]] = nums[i];
            }
            System.arraycopy(output, 0, nums, 0, nums.length);
        }
        
        // Find max gap
        int maxGap = 0;
        for (int i = 1; i < nums.length; i++) {
            maxGap = Math.max(maxGap, nums[i] - nums[i-1]);
        }
        return maxGap;
    }

    // Approach 2: Bucket approach (true O(n))
    public static int maximumGapBucket(int[] nums) {
        int n = nums.length;
        if (n < 2) return 0;
        
        int min = Integer.MAX_VALUE, max = Integer.MIN_VALUE;
        for (int v : nums) { min = Math.min(min, v); max = Math.max(max, v); }
        if (min == max) return 0;
        
        // Bucket size: at least 1
        int bucketSize = Math.max(1, (max - min) / (n - 1));
        int bucketCount = (max - min) / bucketSize + 1;
        
        int[] bucketMin = new int[bucketCount];
        int[] bucketMax = new int[bucketCount];
        boolean[] hasValue = new boolean[bucketCount];
        Arrays.fill(bucketMin, Integer.MAX_VALUE);
        Arrays.fill(bucketMax, Integer.MIN_VALUE);
        
        for (int v : nums) {
            int idx = (v - min) / bucketSize;
            bucketMin[idx] = Math.min(bucketMin[idx], v);
            bucketMax[idx] = Math.max(bucketMax[idx], v);
            hasValue[idx] = true;
        }
        
        // Max gap is between consecutive non-empty buckets
        int maxGap = 0, prevMax = bucketMax[0];
        for (int i = 1; i < bucketCount; i++) {
            if (!hasValue[i]) continue;
            maxGap = Math.max(maxGap, bucketMin[i] - prevMax);
            prevMax = bucketMax[i];
        }
        return maxGap;
    }

    public static void main(String[] args) {
        int[] nums1 = {3, 6, 9, 1};
        System.out.println("LeetCode 164: Maximum Gap");
        System.out.println("Input: " + Arrays.toString(nums1));
        System.out.println("Radix approach: " + maximumGapRadix(nums1.clone()));
        System.out.println("Bucket approach: " + maximumGapBucket(nums1.clone()));
        // Sorted: [1,3,6,9], max gap = 3

        int[] nums2 = {10, 1, 100, 3, 2, 50};
        System.out.println("\nInput: " + Arrays.toString(nums2));
        System.out.println("Bucket approach: " + maximumGapBucket(nums2));
        // Sorted: [1,2,3,10,50,100], max gap = 50
    }
}
