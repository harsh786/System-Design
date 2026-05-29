import java.util.*;

public class Problem15_StockPriceFluctuation {
    // 2034. Stock Price Fluctuation.
    
    TreeMap<Integer, Integer> priceCount = new TreeMap<>(); // price -> count
    Map<Integer, Integer> timePrice = new HashMap<>(); // timestamp -> price
    int latestTime = 0;
    
    public void update(int timestamp, int price) {
        if (timePrice.containsKey(timestamp)) {
            int old = timePrice.get(timestamp);
            priceCount.merge(old, -1, Integer::sum);
            if (priceCount.get(old) == 0) priceCount.remove(old);
        }
        timePrice.put(timestamp, price);
        priceCount.merge(price, 1, Integer::sum);
        latestTime = Math.max(latestTime, timestamp);
    }
    
    public int current() { return timePrice.get(latestTime); }
    public int maximum() { return priceCount.lastKey(); }
    public int minimum() { return priceCount.firstKey(); }
    
    public static void main(String[] args) {
        Problem15_StockPriceFluctuation sol = new Problem15_StockPriceFluctuation();
        sol.update(1, 10); sol.update(2, 5);
        System.out.println("Current: " + sol.current()); // 5
        System.out.println("Max: " + sol.maximum());     // 10
        sol.update(1, 3);
        System.out.println("Max: " + sol.maximum());     // 5
        System.out.println("Min: " + sol.minimum());     // 3
    }
}
