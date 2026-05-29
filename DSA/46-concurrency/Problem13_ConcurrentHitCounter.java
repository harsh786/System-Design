/**
 * Problem: Concurrent Hit Counter
 * Count hits in last 5 minutes, thread-safe.
 * 
 * Approach: See implementation below.
 * Time Complexity: O(1) per operation
 * Space Complexity: O(n)
 * 
 * Production Analogy: Real-time analytics dashboard counting requests per window.
 */
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem13_ConcurrentHitCounter {
    private final int[] hits = new int[300];
    private final int[] times = new int[300];

    public synchronized void hit(int timestamp) {
        int idx = timestamp % 300;
        if (times[idx] != timestamp) { times[idx] = timestamp; hits[idx] = 1; }
        else hits[idx]++;
    }

    public synchronized int getHits(int timestamp) {
        int total = 0;
        for (int i = 0; i < 300; i++) {
            if (timestamp - times[i] < 300) total += hits[i];
        }
        return total;
    }

    public static void main(String[] args) {
        Problem13_ConcurrentHitCounter counter = new Problem13_ConcurrentHitCounter();
        counter.hit(1); counter.hit(2); counter.hit(3); counter.hit(3);
        System.out.println("Hits at t=4: " + counter.getHits(4)); // 4
        System.out.println("Hits at t=301: " + counter.getHits(301)); // 3
    }
}
