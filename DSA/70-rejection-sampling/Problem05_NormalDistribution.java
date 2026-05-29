import java.util.*;

/**
 * Problem 5: Rejection Sampling for Normal Distribution
 * 
 * Generate samples from Standard Normal N(0,1) using rejection sampling.
 * 
 * Classic approaches:
 * 1. Box-Muller transform (not rejection, but elegant)
 * 2. Marsaglia's ziggurat method (fast, uses precomputed tables)
 * 3. Rejection from exponential envelope
 * 
 * Here we implement rejection sampling using an exponential envelope
 * on the half-normal, then randomly negate for full normal.
 * 
 * Target: f(x) = (2/√(2π)) * exp(-x²/2) for x >= 0 (half-normal)
 * Proposal: g(x) = exp(-x) for x >= 0 (exponential)
 * M = √(2e/π) ≈ 1.3155
 */
public class Problem05_NormalDistribution {

    static Random rand = new Random();

    // Method 1: Rejection from exponential
    public static double sampleNormalRejection() {
        while (true) {
            // Sample from Exp(1): x = -ln(u)
            double x = -Math.log(rand.nextDouble());
            // Accept with probability exp(-(x-1)²/2)
            double accept = Math.exp(-(x - 1) * (x - 1) / 2);
            if (rand.nextDouble() <= accept) {
                // Randomly negate for full normal
                return rand.nextBoolean() ? x : -x;
            }
        }
    }

    // Method 2: Box-Muller (for comparison - not rejection sampling)
    public static double sampleNormalBoxMuller() {
        double u1 = rand.nextDouble();
        double u2 = rand.nextDouble();
        return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    }

    // Method 3: Marsaglia polar method (rejection-based)
    public static double sampleNormalMarsaglia() {
        while (true) {
            double x = 2.0 * rand.nextDouble() - 1.0;
            double y = 2.0 * rand.nextDouble() - 1.0;
            double s = x * x + y * y;
            if (s > 0 && s < 1) {
                return x * Math.sqrt(-2 * Math.log(s) / s);
            }
        }
    }

    public static void main(String[] args) {
        int trials = 1000000;
        
        // Collect samples and verify statistics
        double sum = 0, sumSq = 0;
        int[] histogram = new int[20]; // -5 to 5 in bins of 0.5
        
        for (int i = 0; i < trials; i++) {
            double x = sampleNormalRejection();
            sum += x;
            sumSq += x * x;
            int bin = (int)((x + 5) * 2);
            if (bin >= 0 && bin < 20) histogram[bin]++;
        }
        
        double mean = sum / trials;
        double variance = sumSq / trials - mean * mean;
        
        System.out.println("Normal Distribution via Rejection Sampling");
        System.out.printf("Mean: %.4f (expected 0)%n", mean);
        System.out.printf("Variance: %.4f (expected 1)%n", variance);
        
        System.out.println("\nHistogram (bell curve shape):");
        int maxBin = Arrays.stream(histogram).max().getAsInt();
        for (int i = 0; i < 20; i++) {
            double lo = -5 + i * 0.5;
            int barLen = histogram[i] * 50 / maxBin;
            System.out.printf("  [%+.1f]: %s%n", lo, "#".repeat(barLen));
        }
    }
}
