import java.util.*;

public class Problem30_CountingSortForBucketedLatency {
    // Sort API latencies into percentile buckets
    public static void analyzeLatency(int[] latenciesMs) {
        int max = 5000; // cap at 5s
        int[] count = new int[max + 1];
        for (int l : latenciesMs) count[Math.min(l, max)]++;
        // Compute percentiles
        int total = latenciesMs.length;
        int cumulative = 0;
        int p50 = -1, p95 = -1, p99 = -1;
        for (int i = 0; i <= max; i++) {
            cumulative += count[i];
            if (p50 < 0 && cumulative >= total * 0.5) p50 = i;
            if (p95 < 0 && cumulative >= total * 0.95) p95 = i;
            if (p99 < 0 && cumulative >= total * 0.99) p99 = i;
        }
        System.out.println("p50=" + p50 + "ms, p95=" + p95 + "ms, p99=" + p99 + "ms");
    }

    public static void main(String[] args) {
        Random rand = new Random(42);
        int[] latencies = new int[10000];
        for (int i = 0; i < latencies.length; i++) latencies[i] = (int)(Math.abs(rand.nextGaussian()) * 100 + 50);
        analyzeLatency(latencies);
    }
}
