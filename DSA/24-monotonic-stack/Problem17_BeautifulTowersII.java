import java.util.*;

/**
 * Problem 17: Beautiful Towers II (LeetCode 2866)
 * 
 * Same as Beautiful Towers I but with larger constraints (n up to 10^5).
 * The monotonic stack approach from Problem 16 already handles this in O(n).
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Same as Problem 16 - optimal resource allocation curve.
 */
public class Problem17_BeautifulTowersII {
    
    public long maximumSumOfHeights(List<Integer> maxHeights) {
        int n = maxHeights.size();
        long[] left = new long[n];
        long[] right = new long[n];
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && maxHeights.get(stack.peek()) >= maxHeights.get(i))
                stack.pop();
            left[i] = (stack.isEmpty() ? (long) maxHeights.get(i) * (i + 1)
                : left[stack.peek()] + (long) maxHeights.get(i) * (i - stack.peek()));
            stack.push(i);
        }
        
        stack.clear();
        for (int i = n - 1; i >= 0; i--) {
            while (!stack.isEmpty() && maxHeights.get(stack.peek()) >= maxHeights.get(i))
                stack.pop();
            right[i] = (stack.isEmpty() ? (long) maxHeights.get(i) * (n - i)
                : right[stack.peek()] + (long) maxHeights.get(i) * (stack.peek() - i));
            stack.push(i);
        }
        
        long ans = 0;
        for (int i = 0; i < n; i++)
            ans = Math.max(ans, left[i] + right[i] - maxHeights.get(i));
        return ans;
    }
    
    public static void main(String[] args) {
        Problem17_BeautifulTowersII sol = new Problem17_BeautifulTowersII();
        System.out.println(sol.maximumSumOfHeights(Arrays.asList(5,3,4,1,1))); // 13
        System.out.println(sol.maximumSumOfHeights(Arrays.asList(6,5,3,9,2,7))); // 22
        System.out.println(sol.maximumSumOfHeights(Arrays.asList(3,2,5,5,2,3))); // 18
    }
}
