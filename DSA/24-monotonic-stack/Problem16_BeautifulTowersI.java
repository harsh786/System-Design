import java.util.*;

/**
 * Problem 16: Beautiful Towers I (LeetCode 2865)
 * 
 * Choose a peak index. Heights must increase up to peak then decrease.
 * Maximize sum of heights (can only decrease existing heights).
 * 
 * Approach: For each index as peak, compute max sum using monotonic stack
 * for left increasing and right decreasing prefixes.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Traffic shaping - finding optimal peak throughput
 * point with gradual ramp-up and ramp-down.
 */
public class Problem16_BeautifulTowersI {
    
    public long maximumSumOfHeights(List<Integer> maxHeights) {
        int n = maxHeights.size();
        long[] left = new long[n];  // max sum ending at i with increasing constraint
        long[] right = new long[n]; // max sum starting at i with decreasing constraint
        
        Deque<Integer> stack = new ArrayDeque<>();
        
        // Left pass: increasing
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && maxHeights.get(stack.peek()) >= maxHeights.get(i)) {
                stack.pop();
            }
            if (stack.isEmpty()) {
                left[i] = (long) maxHeights.get(i) * (i + 1);
            } else {
                left[i] = left[stack.peek()] + (long) maxHeights.get(i) * (i - stack.peek());
            }
            stack.push(i);
        }
        
        stack.clear();
        // Right pass: decreasing (mirror)
        for (int i = n - 1; i >= 0; i--) {
            while (!stack.isEmpty() && maxHeights.get(stack.peek()) >= maxHeights.get(i)) {
                stack.pop();
            }
            if (stack.isEmpty()) {
                right[i] = (long) maxHeights.get(i) * (n - i);
            } else {
                right[i] = right[stack.peek()] + (long) maxHeights.get(i) * (stack.peek() - i);
            }
            stack.push(i);
        }
        
        long ans = 0;
        for (int i = 0; i < n; i++) {
            ans = Math.max(ans, left[i] + right[i] - maxHeights.get(i));
        }
        return ans;
    }
    
    public static void main(String[] args) {
        Problem16_BeautifulTowersI sol = new Problem16_BeautifulTowersI();
        
        System.out.println(sol.maximumSumOfHeights(Arrays.asList(5,3,4,1,1))); // 13
        System.out.println(sol.maximumSumOfHeights(Arrays.asList(6,5,3,9,2,7))); // 22
        System.out.println(sol.maximumSumOfHeights(Arrays.asList(3,2,5,5,2,3))); // 18
    }
}
