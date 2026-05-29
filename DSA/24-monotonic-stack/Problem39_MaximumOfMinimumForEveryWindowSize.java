import java.util.*;

/**
 * Problem 39: Maximum of Minimum for Every Window Size
 * 
 * For each window size w (1 to n), find max of all minimums of windows of size w.
 * 
 * Approach: For each element, find its span (distance between PSE and NSE).
 * Element arr[i] is the answer for window size = span. Fill gaps downward.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: SLA guarantees - for each time window duration,
 * what's the best worst-case performance guarantee?
 */
public class Problem39_MaximumOfMinimumForEveryWindowSize {
    
    public int[] maxOfMinForEveryWindow(int[] arr) {
        int n = arr.length;
        int[] left = new int[n], right = new int[n];
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && arr[stack.peek()] >= arr[i]) stack.pop();
            left[i] = stack.isEmpty() ? -1 : stack.peek();
            stack.push(i);
        }
        stack.clear();
        for (int i = n - 1; i >= 0; i--) {
            while (!stack.isEmpty() && arr[stack.peek()] >= arr[i]) stack.pop();
            right[i] = stack.isEmpty() ? n : stack.peek();
            stack.push(i);
        }
        
        int[] result = new int[n + 1]; // result[w] = answer for window size w
        for (int i = 0; i < n; i++) {
            int windowSize = right[i] - left[i] - 1;
            result[windowSize] = Math.max(result[windowSize], arr[i]);
        }
        
        // Fill gaps: result[w] >= result[w+1]
        for (int w = n - 1; w >= 1; w--) {
            result[w] = Math.max(result[w], result[w + 1]);
        }
        
        return Arrays.copyOfRange(result, 1, n + 1);
    }
    
    public static void main(String[] args) {
        Problem39_MaximumOfMinimumForEveryWindowSize sol = new Problem39_MaximumOfMinimumForEveryWindowSize();
        
        System.out.println(Arrays.toString(sol.maxOfMinForEveryWindow(new int[]{10,20,30,50,10,70,30})));
        // [70,30,20,10,10,10,10]
        
        System.out.println(Arrays.toString(sol.maxOfMinForEveryWindow(new int[]{1,2,3,4,5})));
        // [5,4,3,2,1]
    }
}
