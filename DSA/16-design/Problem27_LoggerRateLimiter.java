import java.util.*;

/**
 * Problem 27: Logger Rate Limiter
 * 
 * API Contract:
 * - shouldPrintMessage(timestamp, message): Return true if message hasn't been
 *   printed in last 10 seconds. Record it.
 * 
 * Complexity: O(1)
 * Data Structure: HashMap<message, lastTimestamp>
 * 
 * Production Analogy: Log deduplication (Datadog, Splunk), alert fatigue prevention,
 * notification rate limiting, error grouping in Sentry
 */
public class Problem27_LoggerRateLimiter {

    static class Logger {
        private Map<String, Integer> map;

        public Logger() { map = new HashMap<>(); }

        public boolean shouldPrintMessage(int timestamp, String message) {
            if (map.containsKey(message) && timestamp - map.get(message) < 10)
                return false;
            map.put(message, timestamp);
            return true;
        }
    }

    public static void main(String[] args) {
        Logger logger = new Logger();
        assert logger.shouldPrintMessage(1, "foo");
        assert logger.shouldPrintMessage(2, "bar");
        assert !logger.shouldPrintMessage(3, "foo");
        assert !logger.shouldPrintMessage(8, "bar");
        assert !logger.shouldPrintMessage(10, "foo");
        assert logger.shouldPrintMessage(11, "foo"); // exactly 10 secs later

        System.out.println("All tests passed!");
    }
}
