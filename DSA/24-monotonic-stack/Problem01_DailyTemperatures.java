import java.util.*;

/**
 * Problem 1: Daily Temperatures (LeetCode 739)
 * 
 * Given an array of daily temperatures, return an array where answer[i] is the number
 * of days you have to wait after the ith day to get a warmer temperature.
 * 
 * Monotonic Invariant: Maintain a DECREASING stack of indices. When we encounter a
 * temperature higher than stack top, we pop and record the distance.
 * 
 * Amortized Analysis: Each element is pushed and popped at most once -> O(n) total.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Like a metrics monitoring system that alerts when a threshold
 * is exceeded - "how long until CPU usage exceeds current level?"
 */
public class Problem01_DailyTemperatures {
    
    public int[] dailyTemperatures(int[] temperatures) {
        int n = temperatures.length;
        int[] answer = new int[n];
        Deque<Integer> stack = new ArrayDeque<>(); // stores indices, decreasing temps
        
        for (int i = 0; i < n; i++) {
            // Pop all days that found their warmer day (today)
            while (!stack.isEmpty() && temperatures[i] > temperatures[stack.peek()]) {
                int prev = stack.pop();
                answer[prev] = i - prev;
            }
            stack.push(i);
        }
        // Remaining indices in stack have no warmer day -> answer stays 0
        return answer;
    }
    
    public static void main(String[] args) {
        Problem01_DailyTemperatures sol = new Problem01_DailyTemperatures();
        
        // Test 1: Normal case
        System.out.println(Arrays.toString(sol.dailyTemperatures(new int[]{73,74,75,71,69,72,76,73})));
        // Expected: [1,1,4,2,1,1,0,0]
        
        // Test 2: Decreasing - no warmer days
        System.out.println(Arrays.toString(sol.dailyTemperatures(new int[]{5,4,3,2,1})));
        // Expected: [0,0,0,0,0]
        
        // Test 3: Increasing - always next day
        System.out.println(Arrays.toString(sol.dailyTemperatures(new int[]{1,2,3,4,5})));
        // Expected: [1,1,1,1,0]
        
        // Test 4: Single element
        System.out.println(Arrays.toString(sol.dailyTemperatures(new int[]{50})));
        // Expected: [0]
        
        // Test 5: All same
        System.out.println(Arrays.toString(sol.dailyTemperatures(new int[]{70,70,70})));
        // Expected: [0,0,0]
    }
}
