import java.util.*;

/**
 * Problem 38: Nearest Smaller to Right (Next Smaller Element)
 * 
 * Same as Problem 33 but returning index.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Finding next dip point for auto-scaling decisions.
 */
public class Problem38_NearestSmallerToRight {
    
    public int[] nearestSmallerToRight(int[] arr) {
        int n = arr.length;
        int[] result = new int[n]; // index of NSE
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = n - 1; i >= 0; i--) {
            while (!stack.isEmpty() && arr[stack.peek()] >= arr[i]) stack.pop();
            result[i] = stack.isEmpty() ? -1 : stack.peek();
            stack.push(i);
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem38_NearestSmallerToRight sol = new Problem38_NearestSmallerToRight();
        System.out.println(Arrays.toString(sol.nearestSmallerToRight(new int[]{4,5,2,10,8})));
        // [2,2,-1,4,-1]
        System.out.println(Arrays.toString(sol.nearestSmallerToRight(new int[]{1,2,3})));
        // [-1,-1,-1]
    }
}
