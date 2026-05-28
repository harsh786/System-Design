import java.util.*;

/**
 * Problem 4: Daily Temperatures (LeetCode 739)
 * 
 * Given daily temperatures, return how many days you'd have to wait for a warmer temperature.
 * 
 * Approach: Monotonic decreasing stack storing indices. When a warmer day is found,
 * pop all smaller temperatures and compute the difference.
 * Time Complexity: O(n) - each element pushed/popped at most once
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like monitoring system alerts - "how long until metric exceeds threshold?"
 */
public class Problem04_DailyTemperatures {

    public static int[] dailyTemperatures(int[] temperatures) {
        int n = temperatures.length;
        int[] result = new int[n];
        Deque<Integer> stack = new ArrayDeque<>(); // monotonic decreasing stack of indices
        
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && temperatures[i] > temperatures[stack.peek()]) {
                int idx = stack.pop();
                result[idx] = i - idx;
            }
            stack.push(i);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(dailyTemperatures(new int[]{73,74,75,71,69,72,76,73})));
        // [1,1,4,2,1,1,0,0]
        System.out.println(Arrays.toString(dailyTemperatures(new int[]{30,40,50,60})));
        // [1,1,1,0]
        System.out.println(Arrays.toString(dailyTemperatures(new int[]{30,20,10})));
        // [0,0,0]
    }
}
