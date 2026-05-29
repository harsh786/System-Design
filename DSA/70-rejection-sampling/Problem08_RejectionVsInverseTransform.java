import java.util.*;

/**
 * Problem 8: Rejection Sampling vs Inverse Transform Method
 * 
 * Two fundamental approaches for sampling from a distribution:
 * 
 * Inverse Transform:
 * - Compute CDF F(x), then F^(-1)(U) where U ~ Uniform(0,1)
 * - Always produces one sample per uniform draw (no waste)
 * - Requires closed-form inverse CDF (not always available)
 * 
 * Rejection Sampling:
 * - Only needs to evaluate PDF (not invert CDF)
 * - Wastes samples (1/M efficiency)
 * - Works for any distribution where PDF is computable
 * 
 * Trade-offs and when to use each.
 */
public class Problem08_RejectionVsInverseTransform {

    static Random rand = new Random(42);

    // === EXPONENTIAL DISTRIBUTION ===
    // Inverse CDF: F^(-1)(u) = -ln(1-u)/λ = -ln(u)/λ
    
    static double expInverseTransform(double lambda) {
        return -Math.log(rand.nextDouble()) / lambda;
    }

    static double expRejection(double lambda) {
        // Using uniform[0, 10/λ] as proposal (wasteful but demonstrates concept)
        double range = 10.0 / lambda;
        double M = lambda; // max of PDF
        while (true) {
            double x = rand.nextDouble() * range;
            double fx = lambda * Math.exp(-lambda * x);
            if (rand.nextDouble() * M <= fx) return x;
        }
    }

    // === CAUCHY DISTRIBUTION ===
    // CDF: F(x) = 1/π * arctan(x) + 1/2
    // Inverse: F^(-1)(u) = tan(π(u - 1/2))
    
    static double cauchyInverseTransform() {
        return Math.tan(Math.PI * (rand.nextDouble() - 0.5));
    }

    // === DISTRIBUTION WITHOUT CLOSED-FORM INVERSE ===
    // f(x) = C * sin²(x) on [0, π] (only rejection works easily)
    
    static double sinSquaredRejection() {
        double M = 1.0; // max of sin²(x) = 1
        while (true) {
            double x = rand.nextDouble() * Math.PI; // Uniform[0, π]
            double fx = Math.sin(x) * Math.sin(x);
            if (rand.nextDouble() * M <= fx) return x;
        }
    }

    public static void main(String[] args) {
        int trials = 1000000;
        
        System.out.println("Rejection Sampling vs Inverse Transform");
        System.out.println("========================================\n");

        // Exponential: both methods work
        double lambda = 2.0;
        long t1 = System.nanoTime();
        double sum1 = 0;
        for (int i = 0; i < trials; i++) sum1 += expInverseTransform(lambda);
        long time1 = System.nanoTime() - t1;

        long t2 = System.nanoTime();
        double sum2 = 0;
        for (int i = 0; i < trials; i++) sum2 += expRejection(lambda);
        long time2 = System.nanoTime() - t2;

        System.out.println("Exponential(λ=2), expected mean = 0.5:");
        System.out.printf("  Inverse Transform: mean=%.4f, time=%.1f ms%n", sum1/trials, time1/1e6);
        System.out.printf("  Rejection:         mean=%.4f, time=%.1f ms%n%n", sum2/trials, time2/1e6);

        // sin²(x) on [0,π]: only rejection works easily
        double sum3 = 0;
        for (int i = 0; i < trials; i++) sum3 += sinSquaredRejection();
        System.out.printf("sin²(x) on [0,π], expected mean = π/2:%n");
        System.out.printf("  Rejection: mean=%.4f (expected %.4f)%n", sum3/trials, Math.PI/2);

        System.out.println("\n=== When to use each ===");
        System.out.println("Inverse Transform: CDF inverse is known, need guaranteed O(1)");
        System.out.println("Rejection: Arbitrary PDFs, no closed-form CDF needed");
    }
}
