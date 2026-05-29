import java.util.*;

/**
 * Problem 4: Rejection Sampling Basic Concepts
 * 
 * Rejection Sampling: Generate samples from a target distribution f(x) using
 * a proposal distribution g(x) that we can easily sample from.
 * 
 * Algorithm:
 * 1. Find constant M such that f(x) <= M * g(x) for all x
 * 2. Generate x from g(x)
 * 3. Generate u from Uniform(0, 1)
 * 4. Accept x if u <= f(x) / (M * g(x)), else reject and retry
 * 
 * Efficiency = 1/M (lower M = fewer rejections)
 * 
 * Example: Sample from triangular distribution using uniform proposal.
 */
public class Problem04_RejectionSamplingBasic {

    // Target: Triangular distribution on [0,1] with peak at 0.5
    // f(x) = 4x for x in [0, 0.5], 4(1-x) for x in [0.5, 1]
    // Max of f(x) = 2 (at x=0.5)
    
    // Proposal: Uniform on [0,1], g(x) = 1
    // M = max(f(x)/g(x)) = 2
    
    static Random rand = new Random(42);

    static double targetPDF(double x) {
        if (x < 0 || x > 1) return 0;
        return x <= 0.5 ? 4 * x : 4 * (1 - x);
    }

    public static double sampleTriangular() {
        double M = 2.0;
        while (true) {
            double x = rand.nextDouble(); // From proposal (uniform [0,1])
            double u = rand.nextDouble();
            
            // Accept if u <= f(x) / (M * g(x)) = f(x) / 2
            if (u <= targetPDF(x) / M) {
                return x;
            }
        }
    }

    // Generic rejection sampler
    public static double rejectionSample(
            java.util.function.DoubleUnaryOperator targetPDF,
            java.util.function.DoubleSupplier proposalSampler,
            java.util.function.DoubleUnaryOperator proposalPDF,
            double M) {
        while (true) {
            double x = proposalSampler.getAsDouble();
            double u = rand.nextDouble();
            if (u <= targetPDF.applyAsDouble(x) / (M * proposalPDF.applyAsDouble(x))) {
                return x;
            }
        }
    }

    public static void main(String[] args) {
        int trials = 100000;
        int bins = 10;
        int[] histogram = new int[bins];
        
        for (int i = 0; i < trials; i++) {
            double sample = sampleTriangular();
            int bin = Math.min((int)(sample * bins), bins - 1);
            histogram[bin]++;
        }
        
        System.out.println("Rejection Sampling: Triangular Distribution");
        System.out.println("Acceptance rate: 1/M = 50%");
        System.out.println("\nHistogram (should be triangular/pyramid shape):");
        int maxCount = Arrays.stream(histogram).max().getAsInt();
        for (int i = 0; i < bins; i++) {
            int barLen = histogram[i] * 40 / maxCount;
            System.out.printf("  [%.1f-%.1f]: %s %d%n", 
                i*0.1, (i+1)*0.1, "#".repeat(barLen), histogram[i]);
        }
    }
}
