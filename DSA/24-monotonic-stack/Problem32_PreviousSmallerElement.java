import java.util.*;

/**
 * Problem 32: Previous Smaller Element
 * 
 * For each element, find the nearest smaller element to its left.
 * 
 * Monotonic Invariant: Increasing stack. Pop elements >= current to find PSE.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Finding the last time a metric dropped below current value.
 */
public class Problem32_PreviousSmallerElement {
    
    public int[] previousSmaller(int[] arr) {
        int n = arr.length;
        int[] result = new int[n];
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && stack.peek() >= arr[i]) stack.pop();
            result[i] = stack.isEmpty() ? -1 : stack.peek();
            stack.push(arr[i]);
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem32_PreviousSmallerElement sol = new Problem32_PreviousSmallerElement();
        
        System.out.println(Arrays.toString(sol.previousSmaller(new int[]{4,5,2,10,8}))); // [-1,4,-1,2,2]
        System.out.println(Arrays.toString(sol.previousSmaller(new int[]{3,2,1})));      // [-1,-1,-1]
        System.out.println(Arrays.toString(sol.previousSmaller(new int[]{1,2,3})));      // [-1,1,2]
    }
}
