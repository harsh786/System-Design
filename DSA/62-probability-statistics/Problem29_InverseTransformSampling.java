import java.util.*;

public class Problem29_InverseTransformSampling {
    /* Sample from exponential distribution using inverse CDF */
    private Random rand = new Random();

    public double sampleExponential(double lambda) {
        return -Math.log(1 - rand.nextDouble()) / lambda;
    }

    public static void main(String[] args) {
        Problem29_InverseTransformSampling sol = new Problem29_InverseTransformSampling();
        double sum = 0; int n = 100000;
        for (int i = 0; i < n; i++) sum += sol.sampleExponential(2.0);
        System.out.printf("Mean (expected 0.5): %.4f%n", sum / n);
    }
}
