import java.util.*;

/**
 * Problem 33: Next Smaller Element
 * 
 * For each element, find the nearest smaller element to its right.
 * 
 * Monotonic Invariant: Increasing stack from right, or decreasing stack from left
 * that pops when smaller arrives.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Predicting next dip in resource usage after current level.
 */
public class Problem33_NextSmallerElement {
    
    public int[] nextSmaller(int[] arr) {
        int n = arr.length;
        int[] result = new int[n];
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = n - 1; i >= 0; i--) {
            while (!stack.isEmpty() && stack.peek() >= arr[i]) stack.pop();
            result[i] = stack.isEmpty() ? -1 : stack.peek();
            stack.push(arr[i]);
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem33_NextSmallerElement sol = new Problem33_NextSmallerElement();
        
        System.out.println(Arrays.toString(sol.nextSmaller(new int[]{4,5,2,10,8}))); // [2,2,-1,8,-1]
        System.out.println(Arrays.toString(sol.nextSmaller(new int[]{3,2,1})));      // [2,1,-1]
        System.out.println(Arrays.toString(sol.nextSmaller(new int[]{1,2,3})));      // [-1,-1,-1]
    }
}
