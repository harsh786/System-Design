import java.util.*;

/**
 * Problem 7: Sort Array with Radix Sort (LeetCode 912 variant)
 * 
 * Sort an array using radix sort. Handle edge cases:
 * - Empty array
 * - Single element
 * - All same elements
 * - Negative numbers
 * - Large range of values
 * 
 * Optimization: Use base-65536 (2 passes for 32-bit) for better performance.
 */
public class Problem07_SortArrayRadixSort {

    public static int[] sortArray(int[] nums) {
        if (nums.length <= 1) return nums;
        
        // Handle negatives: offset
        int min = Integer.MAX_VALUE;
        for (int v : nums) min = Math.min(min, v);
        if (min < 0) {
            for (int i = 0; i < nums.length; i++) nums[i] -= min;
        }
        
        // Use base-65536 (16-bit chunks) - only 2 passes for 32-bit integers
        radixSort65536(nums);
        
        // Restore offset
        if (min < 0) {
            for (int i = 0; i < nums.length; i++) nums[i] += min;
        }
        return nums;
    }

    private static void radixSort65536(int[] arr) {
        int n = arr.length;
        int[] aux = new int[n];
        int BASE = 65536;
        
        // Pass 1: lower 16 bits
        int[] count = new int[BASE + 1];
        for (int v : arr) count[(v & 0xFFFF) + 1]++;
        for (int i = 1; i <= BASE; i++) count[i] += count[i-1];
        for (int v : arr) aux[count[v & 0xFFFF]++] = v;
        System.arraycopy(aux, 0, arr, 0, n);
        
        // Pass 2: upper 16 bits
        Arrays.fill(count, 0);
        for (int v : arr) count[((v >>> 16) & 0xFFFF) + 1]++;
        for (int i = 1; i <= BASE; i++) count[i] += count[i-1];
        for (int v : arr) aux[count[(v >>> 16) & 0xFFFF]++] = v;
        System.arraycopy(aux, 0, arr, 0, n);
    }

    public static void main(String[] args) {
        // Test cases
        int[][] tests = {
            {5, 2, 3, 1},
            {5, 1, 1, 2, 0, 0},
            {-4, 0, 7, 4, 9, -5, -1, 0, -7, -1},
            {},
            {1},
            {3, 3, 3}
        };
        
        System.out.println("Sort Array using Radix Sort");
        for (int[] test : tests) {
            int[] sorted = sortArray(test.clone());
            System.out.println(Arrays.toString(test) + " → " + Arrays.toString(sorted));
            for (int i = 1; i < sorted.length; i++) assert sorted[i] >= sorted[i-1];
        }
        System.out.println("All PASS");
    }
}
