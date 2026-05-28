import java.util.*;

/**
 * Problem 33: Stock Price Fluctuation (LeetCode 2034)
 * 
 * Approach: TreeMap for timestamp->price, max-heap and min-heap with lazy deletion.
 * 
 * Time Complexity: O(log N) per operation
 * Space Complexity: O(N)
 * 
 * Production Analogy: Real-time price feed with corrections - maintaining current,
 * max, and min prices with out-of-order updates.
 */
public class Problem33_StockPriceFluctuation {
    
    private Map<Integer, Integer> tsToPrice = new HashMap<>();
    private TreeMap<Integer, Integer> priceCounts = new TreeMap<>();
    private int latestTs = 0;
    
    public void update(int timestamp, int price) {
        if (tsToPrice.containsKey(timestamp)) {
            int oldPrice = tsToPrice.get(timestamp);
            int cnt = priceCounts.get(oldPrice);
            if (cnt == 1) priceCounts.remove(oldPrice);
            else priceCounts.put(oldPrice, cnt - 1);
        }
        tsToPrice.put(timestamp, price);
        priceCounts.merge(price, 1, Integer::sum);
        latestTs = Math.max(latestTs, timestamp);
    }
    
    public int current() { return tsToPrice.get(latestTs); }
    public int maximum() { return priceCounts.lastKey(); }
    public int minimum() { return priceCounts.firstKey(); }
    
    public static void main(String[] args) {
        Problem33_StockPriceFluctuation sp = new Problem33_StockPriceFluctuation();
        sp.update(1, 10);
        sp.update(2, 5);
        System.out.println(sp.current());  // 5
        System.out.println(sp.maximum());  // 10
        sp.update(1, 3); // correct timestamp 1
        System.out.println(sp.maximum());  // 5
        System.out.println(sp.minimum());  // 3
    }
}
