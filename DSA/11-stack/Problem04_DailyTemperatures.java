import java.util.*;

/**
 * Problem 4: Daily Temperatures (LeetCode 739)
 * 
 * Given temperatures array, return array where answer[i] is the number of days
 * you have to wait after day i to get a warmer temperature.
 * 
 * Approach: Monotonic decreasing stack storing indices. When a warmer temp found,
 * pop all smaller temps and calculate days difference.
 * 
 * Time Complexity: O(n) - each index pushed and popped at most once
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like alerting systems that need to find the next threshold breach
 * event. Also similar to stock price monitoring for "next higher price" notifications.
 */
public class Problem04_DailyTemperatures {

    public static int[] dailyTemperatures(int[] temperatures) {
        int n = temperatures.length;
        int[] result = new int[n];
        Deque<Integer> stack = new ArrayDeque<>(); // stores indices
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
        System.out.println(Arrays.toString(dailyTemperatures(new int[]{30,60,90})));
        // [1,1,0]
    }
}
