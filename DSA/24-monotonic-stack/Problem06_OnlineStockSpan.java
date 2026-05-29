import java.util.*;

/**
 * Problem 6: Online Stock Span (LeetCode 901)
 * 
 * Design a class that collects daily price quotes and returns the span
 * (consecutive days where price was <= today's price, including today).
 * 
 * Monotonic Invariant: Decreasing stack of (price, span) pairs.
 * When new price >= stack top, pop and accumulate spans.
 * 
 * Time: O(1) amortized per call, Space: O(n)
 * 
 * Production Analogy: Real stock span indicator used in technical analysis.
 * Measures how long a stock has been at or below current price.
 */
public class Problem06_OnlineStockSpan {
    
    private Deque<int[]> stack; // [price, span]
    
    public Problem06_OnlineStockSpan() {
        stack = new ArrayDeque<>();
    }
    
    public int next(int price) {
        int span = 1;
        while (!stack.isEmpty() && stack.peek()[0] <= price) {
            span += stack.pop()[1];
        }
        stack.push(new int[]{price, span});
        return span;
    }
    
    public static void main(String[] args) {
        Problem06_OnlineStockSpan sol = new Problem06_OnlineStockSpan();
        
        // Test: [100, 80, 60, 70, 60, 75, 85]
        System.out.println(sol.next(100)); // 1
        System.out.println(sol.next(80));  // 1
        System.out.println(sol.next(60));  // 1
        System.out.println(sol.next(70));  // 2
        System.out.println(sol.next(60));  // 1
        System.out.println(sol.next(75));  // 4
        System.out.println(sol.next(85));  // 6
    }
}
