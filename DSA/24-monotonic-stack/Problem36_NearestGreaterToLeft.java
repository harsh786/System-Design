import java.util.*;

/**
 * Problem 36: Nearest Greater to Left (Previous Greater Element)
 * 
 * For each element, find nearest greater element to its left.
 * 
 * Monotonic Invariant: Decreasing stack. Pop elements <= current.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Finding the last peak that exceeded current load level.
 */
public class Problem36_NearestGreaterToLeft {
    
    public int[] nearestGreaterToLeft(int[] arr) {
        int n = arr.length;
        int[] result = new int[n];
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && stack.peek() <= arr[i]) stack.pop();
            result[i] = stack.isEmpty() ? -1 : stack.peek();
            stack.push(arr[i]);
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem36_NearestGreaterToLeft sol = new Problem36_NearestGreaterToLeft();
        System.out.println(Arrays.toString(sol.nearestGreaterToLeft(new int[]{1,3,2,4})));
        // [-1,-1,3,-1]
        System.out.println(Arrays.toString(sol.nearestGreaterToLeft(new int[]{4,3,2,1})));
        // [-1,4,3,2]
        System.out.println(Arrays.toString(sol.nearestGreaterToLeft(new int[]{1,2,3,4})));
        // [-1,-1,-1,-1]
    }
}
