import java.util.*;

/**
 * Problem 35: Nearest Smaller to Left
 * 
 * Same as Previous Smaller Element (Problem 32). Find nearest smaller to left.
 * Returns the index (not value) for more utility.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Finding previous baseline for anomaly detection.
 */
public class Problem35_NearestSmallerToLeft {
    
    public int[] nearestSmallerToLeft(int[] arr) {
        int n = arr.length;
        int[] result = new int[n]; // stores index, -1 if none
        Deque<Integer> stack = new ArrayDeque<>(); // indices
        
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && arr[stack.peek()] >= arr[i]) stack.pop();
            result[i] = stack.isEmpty() ? -1 : stack.peek();
            stack.push(i);
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem35_NearestSmallerToLeft sol = new Problem35_NearestSmallerToLeft();
        System.out.println(Arrays.toString(sol.nearestSmallerToLeft(new int[]{1,6,4,10,2,5})));
        // [-1,0,0,2,0,4]
        System.out.println(Arrays.toString(sol.nearestSmallerToLeft(new int[]{5,4,3,2,1})));
        // [-1,-1,-1,-1,-1]
    }
}
