import java.util.*;

/**
 * Problem 26: Logger Rate Limiter
 * Design a logger that receives messages and returns true if the message should be printed
 * (not printed in the last 10 seconds).
 *
 * Time Complexity: O(1)
 * Space Complexity: O(n) number of unique messages
 *
 * Production Analogy: THIS IS rate limiting. Used in API gateways, log deduplication,
 * alert suppression in monitoring systems (PagerDuty snooze).
 */
public class Problem26_LoggerRateLimiter {
    private Map<String, Integer> lastPrinted = new HashMap<>();

    public boolean shouldPrintMessage(int timestamp, String message) {
        if (timestamp < lastPrinted.getOrDefault(message, -10) + 10) return false;
        lastPrinted.put(message, timestamp);
        return true;
    }

    public static void main(String[] args) {
        Problem26_LoggerRateLimiter logger = new Problem26_LoggerRateLimiter();
        System.out.println(logger.shouldPrintMessage(1, "foo")); // true
        System.out.println(logger.shouldPrintMessage(2, "bar")); // true
        System.out.println(logger.shouldPrintMessage(3, "foo")); // false
        System.out.println(logger.shouldPrintMessage(8, "bar")); // false
        System.out.println(logger.shouldPrintMessage(10, "foo")); // false
        System.out.println(logger.shouldPrintMessage(11, "foo")); // true
    }
}
