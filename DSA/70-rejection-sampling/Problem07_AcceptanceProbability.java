import java.util.*;

/**
 * Problem 7: Acceptance Probability Analysis
 * 
 * The efficiency of rejection sampling depends on the acceptance rate = 1/M.
 * 
 * Analysis:
 * - M = sup(f(x)/g(x)) - the tighter the envelope, the better
 * - Expected samples needed = M (geometric distribution)
 * - Optimal proposal minimizes M
 * 
 * This demonstrates how choice of proposal affects efficiency
 * for sampling from the same target distribution.
 */
public class Problem07_AcceptanceProbability {

    static Random rand = new Random(42);

    interface Distribution {
        double pdf(double x);
        double sample();
    }

    /**
     * Measure acceptance rate empirically and compare with theoretical 1/M
     */
    public static double measureAcceptanceRate(
            java.util.function.DoubleUnaryOperator target,
            Distribution proposal,
            double M, int trials) {
        int accepted = 0;
        for (int i = 0; i < trials; i++) {
            double x = proposal.sample();
            double u = rand.nextDouble();
            if (u <= target.applyAsDouble(x) / (M * proposal.pdf(x))) {
                accepted++;
            }
        }
        return (double) accepted / trials;
    }

    public static void main(String[] args) {
        int trials = 1000000;
        
        // Target: Standard Normal (half, x >= 0)
        java.util.function.DoubleUnaryOperator halfNormal = x -> 
            x >= 0 ? Math.sqrt(2/Math.PI) * Math.exp(-x*x/2) : 0;

        System.out.println("Acceptance Rate Analysis for Half-Normal Distribution");
        System.out.println("=====================================================\n");

        // Proposal 1: Exp(1) - good fit
        double M1 = Math.sqrt(2 * Math.E / Math.PI); // ≈ 1.32
        Distribution exp1 = new Distribution() {
            public double pdf(double x) { return x >= 0 ? Math.exp(-x) : 0; }
            public double sample() { return -Math.log(rand.nextDouble()); }
        };
        double rate1 = measureAcceptanceRate(halfNormal, exp1, M1, trials);
        System.out.printf("Proposal: Exp(1)%n");
        System.out.printf("  Theoretical M = %.4f, acceptance = %.4f%n", M1, 1.0/M1);
        System.out.printf("  Measured acceptance: %.4f%n%n", rate1);

        // Proposal 2: Exp(0.5) - wider, less efficient
        double lambda2 = 0.5;
        // M2 = max(f(x)/(lambda*exp(-lambda*x))) for x>=0
        // At x=0: f(0)/(lambda) = sqrt(2/π)/0.5 ≈ 1.60
        double M2 = Math.sqrt(2/Math.PI) / lambda2;
        Distribution exp05 = new Distribution() {
            public double pdf(double x) { return x >= 0 ? lambda2 * Math.exp(-lambda2*x) : 0; }
            public double sample() { return -Math.log(rand.nextDouble()) / lambda2; }
        };
        double rate2 = measureAcceptanceRate(halfNormal, exp05, M2, trials);
        System.out.printf("Proposal: Exp(0.5)%n");
        System.out.printf("  Theoretical M = %.4f, acceptance = %.4f%n", M2, 1.0/M2);
        System.out.printf("  Measured acceptance: %.4f%n%n", rate2);

        // Proposal 3: Uniform[0, 5] - poor fit for normal tail
        double M3 = Math.sqrt(2/Math.PI) * 5; // f(0) * range
        Distribution unif = new Distribution() {
            public double pdf(double x) { return x >= 0 && x <= 5 ? 0.2 : 0; }
            public double sample() { return rand.nextDouble() * 5; }
        };
        double rate3 = measureAcceptanceRate(halfNormal, unif, M3, trials);
        System.out.printf("Proposal: Uniform[0,5]%n");
        System.out.printf("  Theoretical M = %.4f, acceptance = %.4f%n", M3, 1.0/M3);
        System.out.printf("  Measured acceptance: %.4f%n%n", rate3);

        System.out.println("Conclusion: Better proposal (matching target shape) → higher acceptance rate");
    }
}
