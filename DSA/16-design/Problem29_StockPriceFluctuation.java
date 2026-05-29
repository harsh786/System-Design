import java.util.*;

/**
 * Problem 29: Stock Price Fluctuation
 * 
 * API Contract:
 * - update(timestamp, price): Update/correct price at timestamp
 * - current(): Return latest timestamp's price
 * - maximum(): Return current max price
 * - minimum(): Return current min price
 * 
 * Complexity: update O(log n), current O(1), max/min O(1)
 * Data Structure: HashMap + TreeMap (price -> count) for min/max tracking
 * 
 * Production Analogy: Real-time stock ticker, order book best bid/ask,
 * time-series corrections with late-arriving data
 */
public class Problem29_StockPriceFluctuation {

    static class StockPrice {
        private Map<Integer, Integer> tsToPrice;
        private TreeMap<Integer, Integer> priceCount;
        private int latestTs;

        public StockPrice() {
            tsToPrice = new HashMap<>();
            priceCount = new TreeMap<>();
            latestTs = 0;
        }

        public void update(int timestamp, int price) {
            latestTs = Math.max(latestTs, timestamp);
            if (tsToPrice.containsKey(timestamp)) {
                int oldPrice = tsToPrice.get(timestamp);
                priceCount.merge(oldPrice, -1, Integer::sum);
                if (priceCount.get(oldPrice) == 0) priceCount.remove(oldPrice);
            }
            tsToPrice.put(timestamp, price);
            priceCount.merge(price, 1, Integer::sum);
        }

        public int current() { return tsToPrice.get(latestTs); }
        public int maximum() { return priceCount.lastKey(); }
        public int minimum() { return priceCount.firstKey(); }
    }

    public static void main(String[] args) {
        StockPrice sp = new StockPrice();
        sp.update(1, 10);
        sp.update(2, 5);
        assert sp.current() == 5;
        assert sp.maximum() == 10;
        assert sp.minimum() == 5;
        sp.update(1, 3); // correct timestamp 1
        assert sp.maximum() == 5;
        assert sp.minimum() == 3;
        sp.update(4, 2);
        assert sp.current() == 2;
        assert sp.minimum() == 2;

        System.out.println("All tests passed!");
    }
}
