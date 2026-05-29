/**
 * Problem: Maximum of Minimum for Every Window Size
 * Use stack to find prev/next smaller, then for each element find max window where it's min.
 * Time: O(n) | Space: O(n)
 * Production Analogy: Worst-case guarantee analysis across different SLA windows.
 */
import java.util.*;

public class Problem20_MaxOfMinForEveryWindowSize {
    public static int[] maxOfMin(int[] arr) {
        int n = arr.length;
        int[] left = new int[n], right = new int[n], ans = new int[n + 1];
        Deque<Integer> stack = new ArrayDeque<>();
        for (int i = 0; i < n; i++) { while (!stack.isEmpty() && arr[stack.peek()] >= arr[i]) stack.pop(); left[i] = stack.isEmpty() ? -1 : stack.peek(); stack.push(i); }
        stack.clear();
        for (int i = n - 1; i >= 0; i--) { while (!stack.isEmpty() && arr[stack.peek()] >= arr[i]) stack.pop(); right[i] = stack.isEmpty() ? n : stack.peek(); stack.push(i); }
        for (int i = 0; i < n; i++) { int windowLen = right[i] - left[i] - 1; ans[windowLen] = Math.max(ans[windowLen], arr[i]); }
        for (int i = n - 1; i >= 1; i--) ans[i] = Math.max(ans[i], ans[i + 1]);
        return Arrays.copyOfRange(ans, 1, n + 1);
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(maxOfMin(new int[]{10, 20, 30, 50, 10, 70, 30}))); 
    }
}
