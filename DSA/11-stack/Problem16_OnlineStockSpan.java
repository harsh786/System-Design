import java.util.*;

/**
 * Problem 16: Online Stock Span (LeetCode 901)
 * 
 * Find the span of stock's price for current day (consecutive days where price <= today).
 * 
 * Approach: Monotonic decreasing stack storing (price, span) pairs.
 * When new price >= top, pop and accumulate spans.
 * 
 * Time Complexity: O(1) amortized per call
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like computing rolling maximums in time-series databases
 * for SLA compliance windows (consecutive days meeting SLA).
 */
public class Problem16_OnlineStockSpan {

    static class StockSpanner {
        Deque<int[]> stack = new ArrayDeque<>(); // [price, span]

        public int next(int price) {
            int span = 1;
            while (!stack.isEmpty() && stack.peek()[0] <= price) {
                span += stack.pop()[1];
            }
            stack.push(new int[]{price, span});
            return span;
        }
    }

    public static void main(String[] args) {
        StockSpanner sp = new StockSpanner();
        System.out.println(sp.next(100)); // 1
        System.out.println(sp.next(80));  // 1
        System.out.println(sp.next(60));  // 1
        System.out.println(sp.next(70));  // 2
        System.out.println(sp.next(60));  // 1
        System.out.println(sp.next(75));  // 4
        System.out.println(sp.next(85));  // 6
    }
}
