import java.util.*;

public class Problem50_OnlineStockSpanWithTreeMap {
    // LC 901: Stock Span - consecutive days where price <= today's price
    // Using stack-based approach (classic) but with TreeMap for illustration
    Deque<int[]> stack; // [price, span]

    public Problem50_OnlineStockSpanWithTreeMap() {
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
        Problem50_OnlineStockSpanWithTreeMap ss = new Problem50_OnlineStockSpanWithTreeMap();
        int[] prices = {100, 80, 60, 70, 60, 75, 85};
        for (int p : prices) System.out.print(ss.next(p) + " ");
        // 1 1 1 2 1 4 6
        System.out.println();
    }
}
