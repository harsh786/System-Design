import java.util.*;

public class Problem29_StockPriceFluctuation {
    // LC 2034: Track stock prices with updates, query current/max/min
    Map<Integer, Integer> timePrice;
    TreeMap<Integer, Integer> priceCount;
    int latestTime;

    public Problem29_StockPriceFluctuation() {
        timePrice = new HashMap<>();
        priceCount = new TreeMap<>();
        latestTime = 0;
    }

    public void update(int timestamp, int price) {
        latestTime = Math.max(latestTime, timestamp);
        if (timePrice.containsKey(timestamp)) {
            int old = timePrice.get(timestamp);
            priceCount.merge(old, -1, Integer::sum);
            if (priceCount.get(old) == 0) priceCount.remove(old);
        }
        timePrice.put(timestamp, price);
        priceCount.merge(price, 1, Integer::sum);
    }

    public int current() { return timePrice.get(latestTime); }
    public int maximum() { return priceCount.lastKey(); }
    public int minimum() { return priceCount.firstKey(); }

    public static void main(String[] args) {
        Problem29_StockPriceFluctuation sp = new Problem29_StockPriceFluctuation();
        sp.update(1, 10); sp.update(2, 5);
        System.out.println(sp.current());  // 5
        System.out.println(sp.maximum());  // 10
        sp.update(1, 3);
        System.out.println(sp.maximum());  // 5
        System.out.println(sp.minimum());  // 3
    }
}
