import java.util.*;

/**
 * Problem 34: Find K Closest Elements
 * 
 * Given sorted array, find k closest elements to x.
 * 
 * Approach: Binary search for left bound of the k-element window.
 * Time Complexity: O(log(n-k) + k)
 * Space Complexity: O(k)
 * 
 * Production Analogy: Time-series data retrieval - finding the k data points closest
 * to a given timestamp for interpolation or anomaly context.
 */
public class Problem34_FindKClosestElements {
    
    public List<Integer> findClosestElements(int[] arr, int k, int x) {
        int lo = 0, hi = arr.length - k;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            // Compare distances from both ends of window
            if (x - arr[mid] > arr[mid + k] - x) {
                lo = mid + 1;
            } else {
                hi = mid;
            }
        }
        
        List<Integer> result = new ArrayList<>();
        for (int i = lo; i < lo + k; i++) result.add(arr[i]);
        return result;
    }
    
    public static void main(String[] args) {
        Problem34_FindKClosestElements sol = new Problem34_FindKClosestElements();
        
        System.out.println("Test 1: " + sol.findClosestElements(new int[]{1,2,3,4,5}, 4, 3)); // [1,2,3,4]
        System.out.println("Test 2: " + sol.findClosestElements(new int[]{1,2,3,4,5}, 4, -1)); // [1,2,3,4]
        System.out.println("Test 3: " + sol.findClosestElements(new int[]{1,1,1,10,10,10}, 1, 9)); // [10]
        System.out.println("Test 4: " + sol.findClosestElements(new int[]{0,1,2,3,4,5,6,7,8,9}, 5, 5)); // [3,4,5,6,7]
    }
}
