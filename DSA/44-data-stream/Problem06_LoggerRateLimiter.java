import java.util.*;

public class Problem06_LoggerRateLimiter {
    // 359. Logger Rate Limiter.
    
    Map<String, Integer> map = new HashMap<>();
    
    public boolean shouldPrintMessage(int timestamp, String message) {
        if (map.containsKey(message) && timestamp - map.get(message) < 10) return false;
        map.put(message, timestamp);
        return true;
    }
    
    public static void main(String[] args) {
        Problem06_LoggerRateLimiter sol = new Problem06_LoggerRateLimiter();
        System.out.println(sol.shouldPrintMessage(1, "foo"));  // true
        System.out.println(sol.shouldPrintMessage(2, "bar"));  // true
        System.out.println(sol.shouldPrintMessage(3, "foo"));  // false
        System.out.println(sol.shouldPrintMessage(11, "foo")); // true
    }
}
