import java.util.*;

/**
 * Problem 8: Reservoir Sampling for Log Sampling
 * 
 * In production systems processing millions of requests/second,
 * we can't store all logs. Reservoir sampling maintains a representative
 * sample of k logs from the entire stream.
 * 
 * Use cases:
 * - Error log sampling for debugging
 * - Latency sampling for percentile estimation
 * - Request sampling for load analysis
 * 
 * This implements a log sampling system with stratified sampling
 * (separate reservoirs per log level).
 */
public class Problem08_ReservoirSamplingLogSampling {

    enum LogLevel { DEBUG, INFO, WARN, ERROR }

    static class LogEntry {
        long timestamp;
        LogLevel level;
        String message;
        int latencyMs;
        
        LogEntry(long timestamp, LogLevel level, String message, int latencyMs) {
            this.timestamp = timestamp;
            this.level = level;
            this.message = message;
            this.latencyMs = latencyMs;
        }
    }

    static class LogSampler {
        private Map<LogLevel, LogEntry[]> reservoirs;
        private Map<LogLevel, Integer> counts;
        private int reservoirSize;
        private Random rand;

        LogSampler(int reservoirSize) {
            this.reservoirSize = reservoirSize;
            this.reservoirs = new EnumMap<>(LogLevel.class);
            this.counts = new EnumMap<>(LogLevel.class);
            this.rand = new Random();
            for (LogLevel level : LogLevel.values()) {
                reservoirs.put(level, new LogEntry[reservoirSize]);
                counts.put(level, 0);
            }
        }

        public void addLog(LogEntry entry) {
            LogLevel level = entry.level;
            int count = counts.get(level);
            LogEntry[] reservoir = reservoirs.get(level);
            
            if (count < reservoirSize) {
                reservoir[count] = entry;
            } else {
                int j = rand.nextInt(count + 1);
                if (j < reservoirSize) {
                    reservoir[j] = entry;
                }
            }
            counts.put(level, count + 1);
        }

        /** Estimate p-th percentile latency from sampled logs */
        public int estimatePercentile(LogLevel level, double percentile) {
            LogEntry[] reservoir = reservoirs.get(level);
            int count = Math.min(counts.get(level), reservoirSize);
            int[] latencies = new int[count];
            for (int i = 0; i < count; i++) latencies[i] = reservoir[i].latencyMs;
            Arrays.sort(latencies);
            int idx = (int) (percentile / 100.0 * count);
            return latencies[Math.min(idx, count - 1)];
        }

        public int getCount(LogLevel level) { return counts.get(level); }
    }

    public static void main(String[] args) {
        LogSampler sampler = new LogSampler(1000);
        Random rand = new Random(42);
        
        // Simulate 1M log entries
        int totalLogs = 1_000_000;
        for (int i = 0; i < totalLogs; i++) {
            double r = rand.nextDouble();
            LogLevel level = r < 0.6 ? LogLevel.DEBUG : r < 0.85 ? LogLevel.INFO :
                             r < 0.95 ? LogLevel.WARN : LogLevel.ERROR;
            
            // Latency: normal ~50ms, errors tend to be slower
            int latency = (int) (50 + rand.nextGaussian() * 20);
            if (level == LogLevel.ERROR) latency += 100;
            latency = Math.max(1, latency);
            
            sampler.addLog(new LogEntry(System.currentTimeMillis(), level, 
                "msg_" + i, latency));
        }
        
        System.out.println("Log Sampling with Reservoir Sampling");
        System.out.printf("Total logs processed: %,d%n", totalLogs);
        System.out.println("Reservoir size per level: 1000\n");
        
        System.out.printf("%-8s %-10s %-8s %-8s %-8s%n", "Level", "Total", "P50", "P95", "P99");
        for (LogLevel level : LogLevel.values()) {
            System.out.printf("%-8s %-10d %-8d %-8d %-8d%n", level,
                sampler.getCount(level),
                sampler.estimatePercentile(level, 50),
                sampler.estimatePercentile(level, 95),
                sampler.estimatePercentile(level, 99));
        }
    }
}
