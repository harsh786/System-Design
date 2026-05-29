import java.util.*;

/**
 * Problem 28: Sort Array by Increasing Frequency
 * 
 * Sort by frequency ascending. If same frequency, sort by value descending.
 * 
 * Approach: Count frequencies, custom comparator.
 * Time Complexity: O(n log n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Surfacing rare events first in anomaly detection dashboards -
 * less frequent = more anomalous = higher visibility.
 */
public class Problem28_SortArrayByIncreasingFrequency {
    
    public int[] frequencySort(int[] nums) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int n : nums) freq.merge(n, 1, Integer::sum);
        
        Integer[] arr = new Integer[nums.length];
        for (int i = 0; i < nums.length; i++) arr[i] = nums[i];
        
        Arrays.sort(arr, (a, b) -> {
            int fa = freq.get(a), fb = freq.get(b);
            if (fa != fb) return fa - fb;
            return b - a;
        });
        
        for (int i = 0; i < nums.length; i++) nums[i] = arr[i];
        return nums;
    }
    
    public static void main(String[] args) {
        Problem28_SortArrayByIncreasingFrequency sol = new Problem28_SortArrayByIncreasingFrequency();
        
        System.out.println("Test 1: " + Arrays.toString(sol.frequencySort(new int[]{1,1,2,2,2,3}))); // [3,1,1,2,2,2]
        System.out.println("Test 2: " + Arrays.toString(sol.frequencySort(new int[]{2,3,1,3,2}))); // [1,3,3,2,2]
        System.out.println("Test 3: " + Arrays.toString(sol.frequencySort(new int[]{-1,1,-6,4,5,-6,1,4,1}))); // [5,-1,4,4,-6,-6,1,1,1]
    }
}
