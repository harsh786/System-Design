import java.util.*;

/**
 * Problem 15: Maximum Gap
 * 
 * Given unsorted array, find max difference between successive elements in sorted form.
 * Must run in O(n) time.
 * 
 * Approach: Radix sort or Bucket sort (Pigeonhole principle).
 * Bucket approach: max gap >= ceil((max-min)/(n-1)). Create buckets of this size.
 * Max gap is between max of one bucket and min of next non-empty bucket.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Detecting anomalous gaps in time-series data (e.g., missing heartbeats
 * in distributed system monitoring).
 */
public class Problem15_MaximumGap {
    
    public int maximumGap(int[] nums) {
        int n = nums.length;
        if (n < 2) return 0;
        
        int min = Integer.MAX_VALUE, max = Integer.MIN_VALUE;
        for (int num : nums) { min = Math.min(min, num); max = Math.max(max, num); }
        if (min == max) return 0;
        
        int bucketSize = Math.max(1, (max - min) / (n - 1));
        int bucketCount = (max - min) / bucketSize + 1;
        
        int[] bucketMin = new int[bucketCount];
        int[] bucketMax = new int[bucketCount];
        Arrays.fill(bucketMin, Integer.MAX_VALUE);
        Arrays.fill(bucketMax, Integer.MIN_VALUE);
        
        for (int num : nums) {
            int idx = (num - min) / bucketSize;
            bucketMin[idx] = Math.min(bucketMin[idx], num);
            bucketMax[idx] = Math.max(bucketMax[idx], num);
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
        Problem15_MaximumGap sol = new Problem15_MaximumGap();
        
        System.out.println("Test 1: " + sol.maximumGap(new int[]{3,6,9,1})); // 3
        System.out.println("Test 2: " + sol.maximumGap(new int[]{10})); // 0
        System.out.println("Test 3: " + sol.maximumGap(new int[]{1,1,1,1})); // 0
        System.out.println("Test 4: " + sol.maximumGap(new int[]{1,10000000})); // 9999999
        System.out.println("Test 5: " + sol.maximumGap(new int[]{1,3,100})); // 97
    }
}
