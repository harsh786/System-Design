import java.util.*;

/**
 * Problem 37: Nearest Greater to Right (Next Greater Element)
 * 
 * Classic NGE - find next greater element to the right.
 * 
 * Monotonic Invariant: Decreasing stack from right (or process left-to-right popping).
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Alert system - next time a metric exceeds current threshold.
 */
public class Problem37_NearestGreaterToRight {
    
    public int[] nearestGreaterToRight(int[] arr) {
        int n = arr.length;
        int[] result = new int[n];
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = n - 1; i >= 0; i--) {
            while (!stack.isEmpty() && stack.peek() <= arr[i]) stack.pop();
            result[i] = stack.isEmpty() ? -1 : stack.peek();
            stack.push(arr[i]);
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem37_NearestGreaterToRight sol = new Problem37_NearestGreaterToRight();
        System.out.println(Arrays.toString(sol.nearestGreaterToRight(new int[]{4,5,2,10,8})));
        // [5,10,10,-1,-1]
        System.out.println(Arrays.toString(sol.nearestGreaterToRight(new int[]{1,2,3,4})));
        // [2,3,4,-1]
    }
}
