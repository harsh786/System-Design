import java.util.*;

/**
 * Problem 6: Rejection Sampling for Custom Distributions
 * 
 * Demonstrates rejection sampling for arbitrary distributions:
 * 1. Beta distribution
 * 2. Truncated distributions
 * 3. Mixture distributions
 * 
 * Key principle: As long as you can evaluate f(x) up to a constant,
 * and have a proposal g(x) with M*g(x) >= f(x), rejection sampling works.
 */
public class Problem06_CustomDistributions {

    static Random rand = new Random(42);

    // Beta(a,b) distribution on [0,1] using uniform proposal
    public static double sampleBeta(double alpha, double beta) {
        // f(x) ∝ x^(α-1) * (1-x)^(β-1)
        // Proposal: Uniform[0,1], g(x)=1
        // M = max of f(x) over [0,1]
        double mode = (alpha - 1) / (alpha + beta - 2);
        if (alpha <= 1) mode = 0.001;
        if (beta <= 1) mode = 0.999;
        double M = Math.pow(mode, alpha-1) * Math.pow(1-mode, beta-1);
        
        while (true) {
            double x = rand.nextDouble();
            double fx = Math.pow(x, alpha-1) * Math.pow(1-x, beta-1);
            if (rand.nextDouble() * M <= fx) return x;
        }
    }

    // Truncated normal: N(μ,σ²) restricted to [a,b]
    public static double sampleTruncatedNormal(double mu, double sigma, double a, double b) {
        while (true) {
            // Propose from uniform [a,b]
            double x = a + rand.nextDouble() * (b - a);
            double z = (x - mu) / sigma;
            // Accept with probability proportional to normal PDF
            double accept = Math.exp(-0.5 * z * z);
            if (rand.nextDouble() <= accept) return x;
        }
    }

    // Custom bimodal distribution: mixture of two Gaussians
    public static double sampleBimodal() {
        // f(x) = 0.3*N(-2,0.5) + 0.7*N(2,1)
        // Proposal: Uniform[-5, 5], g(x) = 0.1
        double M = 1.0; // Approximate upper bound of f(x)/g(x)
        while (true) {
            double x = rand.nextDouble() * 10 - 5; // Uniform [-5, 5]
            double fx = 0.3 * normalPDF(x, -2, 0.5) + 0.7 * normalPDF(x, 2, 1);
            if (rand.nextDouble() * M * 0.1 <= fx) return x;
        }
    }

    private static double normalPDF(double x, double mu, double sigma) {
        double z = (x - mu) / sigma;
        return Math.exp(-0.5 * z * z) / (sigma * Math.sqrt(2 * Math.PI));
    }

    public static void main(String[] args) {
        int trials = 100000;
        
        // Beta(2, 5) distribution
        System.out.println("Beta(2,5) - Expected mean: 2/7 ≈ 0.286");
        double sum = 0;
        for (int i = 0; i < trials; i++) sum += sampleBeta(2, 5);
        System.out.printf("Sample mean: %.4f%n%n", sum / trials);
        
        // Truncated Normal
        System.out.println("Truncated Normal N(0,1) on [-1, 1]");
        sum = 0;
        for (int i = 0; i < trials; i++) sum += sampleTruncatedNormal(0, 1, -1, 1);
        System.out.printf("Sample mean: %.4f (expected ~0)%n%n", sum / trials);
        
        // Bimodal
        System.out.println("Bimodal: 30%% N(-2,0.5) + 70%% N(2,1)");
        sum = 0;
        for (int i = 0; i < trials; i++) sum += sampleBimodal();
        System.out.printf("Sample mean: %.4f (expected: 0.3*(-2)+0.7*2 = 0.8)%n", sum / trials);
    }
}
