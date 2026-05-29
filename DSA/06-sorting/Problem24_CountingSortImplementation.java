import java.util.*;

/**
 * Problem 24: Counting Sort Implementation
 * 
 * Sort array of integers in known range using counting sort.
 * 
 * Approach: Count occurrences, compute prefix sums, place elements.
 * Time Complexity: O(n + k) where k = range of values
 * Space Complexity: O(n + k)
 * Stability: Stable (when done with prefix sum approach)
 * 
 * Production Analogy: Sorting HTTP status codes in access logs (known range 100-599),
 * or age-based demographic bucketing for analytics.
 */
public class Problem24_CountingSortImplementation {
    
    public int[] countingSort(int[] nums) {
        if (nums.length == 0) return nums;
        
        int min = Integer.MAX_VALUE, max = Integer.MIN_VALUE;
        for (int n : nums) { min = Math.min(min, n); max = Math.max(max, n); }
        
        int range = max - min + 1;
        int[] count = new int[range];
        for (int n : nums) count[n - min]++;
        
        // Prefix sum for stable sort
        for (int i = 1; i < range; i++) count[i] += count[i - 1];
        
        int[] output = new int[nums.length];
        for (int i = nums.length - 1; i >= 0; i--) {
            output[--count[nums[i] - min]] = nums[i];
        }
        return output;
    }
    
    public static void main(String[] args) {
        Problem24_CountingSortImplementation sol = new Problem24_CountingSortImplementation();
        
        System.out.println("Test 1: " + Arrays.toString(sol.countingSort(new int[]{4,2,2,8,3,3,1}))); // [1,2,2,3,3,4,8]
        System.out.println("Test 2: " + Arrays.toString(sol.countingSort(new int[]{-5,2,-3,0,1}))); // [-5,-3,0,1,2]
        System.out.println("Test 3: " + Arrays.toString(sol.countingSort(new int[]{1,1,1}))); // [1,1,1]
        System.out.println("Test 4: " + Arrays.toString(sol.countingSort(new int[]{}))); // []
    }
}
