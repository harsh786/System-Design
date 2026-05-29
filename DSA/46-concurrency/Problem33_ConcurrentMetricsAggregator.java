import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem33_ConcurrentMetricsAggregator {
    /**
     * Problem: Concurrent Metrics Aggregator
     * Aggregate metrics (count, sum, min, max) from multiple threads.
     * Approach: LongAdder/AtomicLong for lock-free aggregation.
     * Time: O(1) per record | Space: O(metrics)
     * Production Analogy: Prometheus client library aggregating metrics before scrape.
     */
    private final ConcurrentHashMap<String, LongAdder> counts = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, LongAdder> sums = new ConcurrentHashMap<>();

    public void record(String metric, long value) {
        counts.computeIfAbsent(metric, k -> new LongAdder()).increment();
        sums.computeIfAbsent(metric, k -> new LongAdder()).add(value);
    }

    public long getCount(String metric) { LongAdder a = counts.get(metric); return a == null ? 0 : a.sum(); }
    public long getSum(String metric) { LongAdder a = sums.get(metric); return a == null ? 0 : a.sum(); }

    public static void main(String[] args) throws InterruptedException {
        Problem33_ConcurrentMetricsAggregator agg = new Problem33_ConcurrentMetricsAggregator();
        Thread[] ts = new Thread[4];
        for (int i = 0; i < 4; i++) { final int id = i; ts[i] = new Thread(() -> { for (int j = 0; j < 100; j++) agg.record("latency", id * 10 + j); }); ts[i].start(); }
        for (Thread t : ts) t.join();
        System.out.println("Count: " + agg.getCount("latency") + ", Sum: " + agg.getSum("latency"));
    }
}
