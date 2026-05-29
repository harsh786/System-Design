import java.util.*;

/**
 * Problem 46: Sort Transformed Array
 * 
 * Given sorted array and quadratic function f(x) = ax² + bx + c, return sorted transformed values.
 * 
 * Approach: Two pointers from ends. If a >= 0, parabola opens up (max at ends).
 * If a < 0, parabola opens down (min at ends).
 * Time Complexity: O(n)
 * Space Complexity: O(n) for result
 * 
 * Production Analogy: Applying non-linear transformations to sorted sensor data while 
 * maintaining sort order (e.g., distance-to-signal-strength mapping in wireless networks).
 */
public class Problem46_SortTransformedArray {
    
    public int[] sortTransformedArray(int[] nums, int a, int b, int c) {
        int n = nums.length;
        int[] result = new int[n];
        int lo = 0, hi = n - 1;
        int idx = (a >= 0) ? n - 1 : 0;
        
        while (lo <= hi) {
            int fLo = transform(nums[lo], a, b, c);
            int fHi = transform(nums[hi], a, b, c);
            
            if (a >= 0) {
                if (fLo >= fHi) { result[idx--] = fLo; lo++; }
                else { result[idx--] = fHi; hi--; }
            } else {
                if (fLo <= fHi) { result[idx++] = fLo; lo++; }
                else { result[idx++] = fHi; hi--; }
            }
        }
        return result;
    }
    
    private int transform(int x, int a, int b, int c) {
        return a * x * x + b * x + c;
    }
    
    public static void main(String[] args) {
        Problem46_SortTransformedArray sol = new Problem46_SortTransformedArray();
        
        System.out.println("Test 1: " + Arrays.toString(sol.sortTransformedArray(new int[]{-4,-2,2,4}, 1, 3, 5)));
        // [3,9,15,33]
        
        System.out.println("Test 2: " + Arrays.toString(sol.sortTransformedArray(new int[]{-4,-2,2,4}, -1, 3, 5)));
        // [-23,-5,1,7]
        
        System.out.println("Test 3: " + Arrays.toString(sol.sortTransformedArray(new int[]{-1,0,1}, 0, 1, 0)));
        // [-1,0,1]
    }
}
