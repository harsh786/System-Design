import java.util.*;

/**
 * Problem 34: Stock Span Problem (Classic variant)
 * 
 * Given array of stock prices, find span for each day.
 * Span = max consecutive days (including today) price was <= today's price.
 * 
 * Monotonic Invariant: Decreasing stack of indices. Pop elements with price <= current.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Technical indicator for stock trading systems.
 */
public class Problem34_StockSpanProblem {
    
    public int[] calculateSpan(int[] prices) {
        int n = prices.length;
        int[] span = new int[n];
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && prices[stack.peek()] <= prices[i]) stack.pop();
            span[i] = stack.isEmpty() ? i + 1 : i - stack.peek();
            stack.push(i);
        }
        return span;
    }
    
    public static void main(String[] args) {
        Problem34_StockSpanProblem sol = new Problem34_StockSpanProblem();
        
        System.out.println(Arrays.toString(sol.calculateSpan(new int[]{100,80,60,70,60,75,85})));
        // Expected: [1,1,1,2,1,4,6]
        
        System.out.println(Arrays.toString(sol.calculateSpan(new int[]{10,4,5,90,120,80})));
        // Expected: [1,1,2,4,5,1]
    }
}
