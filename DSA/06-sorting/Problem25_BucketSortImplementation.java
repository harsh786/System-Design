import java.util.*;

/**
 * Problem 25: Bucket Sort Implementation
 * 
 * Sort floating point numbers uniformly distributed in [0, 1).
 * 
 * Approach: Distribute into n buckets, sort each bucket, concatenate.
 * Time Complexity: O(n) average when distribution is uniform, O(n²) worst
 * Space Complexity: O(n)
 * Stability: Stable (if bucket internal sort is stable)
 * 
 * Production Analogy: Sharding data by hash range - each shard sorts independently,
 * then results are concatenated. Used in distributed sorting (like Spark's range partitioner).
 */
public class Problem25_BucketSortImplementation {
    
    public double[] bucketSort(double[] nums) {
        int n = nums.length;
        if (n <= 1) return nums;
        
        @SuppressWarnings("unchecked")
        List<Double>[] buckets = new List[n];
        for (int i = 0; i < n; i++) buckets[i] = new ArrayList<>();
        
        for (double num : nums) {
            int idx = (int)(num * n);
            if (idx == n) idx = n - 1;
            buckets[idx].add(num);
        }
        
        int k = 0;
        for (List<Double> bucket : buckets) {
            Collections.sort(bucket);
            for (double val : bucket) nums[k++] = val;
        }
        return nums;
    }
    
    // Generic integer bucket sort
    public int[] bucketSortInts(int[] nums) {
        if (nums.length <= 1) return nums;
        int min = Integer.MAX_VALUE, max = Integer.MIN_VALUE;
        for (int n : nums) { min = Math.min(min, n); max = Math.max(max, n); }
        
        int bucketCount = nums.length;
        int range = max - min + 1;
        @SuppressWarnings("unchecked")
        List<Integer>[] buckets = new List[bucketCount];
        for (int i = 0; i < bucketCount; i++) buckets[i] = new ArrayList<>();
        
        for (int n : nums) {
            int idx = (int)((long)(n - min) * (bucketCount - 1) / range);
            buckets[idx].add(n);
        }
        
        int k = 0;
        for (List<Integer> bucket : buckets) {
            Collections.sort(bucket);
            for (int val : bucket) nums[k++] = val;
        }
        return nums;
    }
    
    public static void main(String[] args) {
        Problem25_BucketSortImplementation sol = new Problem25_BucketSortImplementation();
        
        double[] t1 = {0.78, 0.17, 0.39, 0.26, 0.72, 0.94, 0.21, 0.12, 0.23, 0.68};
        System.out.println("Test 1: " + Arrays.toString(sol.bucketSort(t1)));
        
        System.out.println("Test 2: " + Arrays.toString(sol.bucketSortInts(new int[]{29,25,3,49,9,37,21,43})));
        System.out.println("Test 3: " + Arrays.toString(sol.bucketSortInts(new int[]{1})));
    }
}
