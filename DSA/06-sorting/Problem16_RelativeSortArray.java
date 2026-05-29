import java.util.*;

/**
 * Problem 16: Relative Sort Array
 * 
 * Sort arr1 such that elements appear in same relative order as arr2.
 * Elements not in arr2 go at end in ascending order.
 * 
 * Approach: Counting sort with arr2 as ordering guide.
 * Time Complexity: O(n + m + max_val)
 * Space Complexity: O(max_val)
 * 
 * Production Analogy: Custom sorting API responses based on client-specified field priority order.
 */
public class Problem16_RelativeSortArray {
    
    public int[] relativeSortArray(int[] arr1, int[] arr2) {
        int max = 0;
        for (int n : arr1) max = Math.max(max, n);
        int[] count = new int[max + 1];
        for (int n : arr1) count[n]++;
        
        int idx = 0;
        // Place elements in arr2 order
        for (int n : arr2) {
            while (count[n]-- > 0) arr1[idx++] = n;
        }
        // Place remaining in ascending order
        for (int i = 0; i <= max; i++) {
            while (count[i] > 0) { arr1[idx++] = i; count[i]--; }
        }
        return arr1;
    }
    
    public static void main(String[] args) {
        Problem16_RelativeSortArray sol = new Problem16_RelativeSortArray();
        
        System.out.println("Test 1: " + Arrays.toString(sol.relativeSortArray(
            new int[]{2,3,1,3,2,4,6,7,9,2,19}, new int[]{2,1,4,3,9,6})));
        // [2,2,2,1,4,3,3,9,6,7,19]
        
        System.out.println("Test 2: " + Arrays.toString(sol.relativeSortArray(
            new int[]{28,6,22,8,44,17}, new int[]{22,28,8,6})));
        // [22,28,8,6,17,44]
    }
}
