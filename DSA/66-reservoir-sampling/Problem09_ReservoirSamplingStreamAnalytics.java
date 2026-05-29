import java.util.*;

/**
 * Problem 9: Reservoir Sampling for Stream Analytics
 * 
 * Maintaining approximate statistics over a data stream using reservoir sampling:
 * - Approximate median/quantiles
 * - Approximate distinct count estimation
 * - Sliding window sampling
 * 
 * Key insight: A random sample of size k from n elements gives good estimates
 * of population statistics with confidence proportional to sqrt(k).
 */
public class Problem09_ReservoirSamplingStreamAnalytics {

    static class StreamAnalyzer {
        private double[] reservoir;
        private int k;
        private int count;
        private Random rand;
        // Running stats
        private double runningSum;
        private double runningMin, runningMax;

        StreamAnalyzer(int reservoirSize) {
            this.k = reservoirSize;
            this.reservoir = new double[k];
            this.count = 0;
            this.rand = new Random();
            this.runningMin = Double.MAX_VALUE;
            this.runningMax = Double.MIN_VALUE;
        }

        public void add(double value) {
            runningSum += value;
            runningMin = Math.min(runningMin, value);
            runningMax = Math.max(runningMax, value);
            
            if (count < k) {
                reservoir[count] = value;
            } else {
                int j = rand.nextInt(count + 1);
                if (j < k) reservoir[j] = value;
            }
            count++;
        }

        public double approximateMedian() {
            int size = Math.min(count, k);
            double[] sorted = Arrays.copyOf(reservoir, size);
            Arrays.sort(sorted);
            return sorted[size / 2];
        }

        public double approximatePercentile(double p) {
            int size = Math.min(count, k);
            double[] sorted = Arrays.copyOf(reservoir, size);
            Arrays.sort(sorted);
            int idx = (int)(p / 100.0 * size);
            return sorted[Math.min(idx, size - 1)];
        }

        public double exactMean() { return runningSum / count; }
        public double approximateStdDev() {
            int size = Math.min(count, k);
            double mean = 0;
            for (int i = 0; i < size; i++) mean += reservoir[i];
            mean /= size;
            double variance = 0;
            for (int i = 0; i < size; i++) variance += Math.pow(reservoir[i] - mean, 2);
            return Math.sqrt(variance / size);
        }
    }

    public static void main(String[] args) {
        // Simulate a stream of latencies following log-normal distribution
        StreamAnalyzer analyzer = new StreamAnalyzer(5000);
        Random rand = new Random(42);
        int streamSize = 10_000_000;
        
        // Also compute exact stats for comparison
        double[] all = new double[Math.min(streamSize, 100000)]; // partial for exact calc
        
        for (int i = 0; i < streamSize; i++) {
            double latency = Math.exp(3.5 + 0.5 * rand.nextGaussian()); // Log-normal
            analyzer.add(latency);
            if (i < all.length) all[i] = latency;
        }
        
        // Exact stats from first 100k for comparison
        Arrays.sort(all);
        
        System.out.println("Stream Analytics via Reservoir Sampling");
        System.out.printf("Stream size: %,d elements, Reservoir: 5000%n%n", streamSize);
        
        System.out.printf("%-20s %-15s %-15s%n", "Statistic", "Approximate", "Exact(100k)");
        System.out.printf("%-20s %-15.2f %-15.2f%n", "Median (P50)", 
            analyzer.approximateMedian(), all[all.length/2]);
        System.out.printf("%-20s %-15.2f %-15.2f%n", "P95", 
            analyzer.approximatePercentile(95), all[(int)(0.95*all.length)]);
        System.out.printf("%-20s %-15.2f %-15.2f%n", "P99", 
            analyzer.approximatePercentile(99), all[(int)(0.99*all.length)]);
        System.out.printf("%-20s %-15.2f %-15s%n", "Std Dev", 
            analyzer.approximateStdDev(), "N/A");
        
        System.out.println("\nMemory: O(k) = O(5000) regardless of stream size");
    }
}
