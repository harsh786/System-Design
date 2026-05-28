import java.util.*;

/**
 * Problem 30: Maximum Gap
 * Find max difference between successive elements in sorted form, in O(n) time.
 * 
 * Production Analogy: Like finding the largest gap in time-series data (biggest 
 * downtime period) - bucket sort / pigeonhole principle.
 * 
 * O(n) time, O(n) space - Bucket sort / Radix sort approach
 * Key insight: max gap >= ceil((max-min)/(n-1)), so bucket by this size
 */
public class Problem30_MaximumGap {

    public static int maximumGap(int[] nums) {
        int n = nums.length;
        if (n < 2) return 0;
        int min = Integer.MAX_VALUE, max = Integer.MIN_VALUE;
        for (int v : nums) { min = Math.min(min, v); max = Math.max(max, v); }
        if (min == max) return 0;
        int bucketSize = Math.max(1, (max - min) / (n - 1));
        int bucketCount = (max - min) / bucketSize + 1;
        int[] bucketMin = new int[bucketCount], bucketMax = new int[bucketCount];
        Arrays.fill(bucketMin, Integer.MAX_VALUE);
        Arrays.fill(bucketMax, Integer.MIN_VALUE);
        for (int v : nums) {
            int idx = (v - min) / bucketSize;
            bucketMin[idx] = Math.min(bucketMin[idx], v);
            bucketMax[idx] = Math.max(bucketMax[idx], v);
        }
        int maxGap = 0, prevMax = bucketMax[0];
        for (int i = 1; i < bucketCount; i++) {
            if (bucketMin[i] == Integer.MAX_VALUE) continue;
            maxGap = Math.max(maxGap, bucketMin[i] - prevMax);
            prevMax = bucketMax[i];
        }
        return maxGap;
    }

    public static void main(String[] args) {
        System.out.println(maximumGap(new int[]{3,6,9,1}));  // 3
        System.out.println(maximumGap(new int[]{10}));        // 0
        System.out.println(maximumGap(new int[]{1,10000000}));// 9999999
    }
}
