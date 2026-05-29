import java.util.*;

public class Problem20_PoissonDistribution {
    public double pmf(int k, double lambda) {
        return Math.exp(-lambda) * Math.pow(lambda, k) / factorial(k);
    }

    private double factorial(int n) { double r = 1; for (int i = 2; i <= n; i++) r *= i; return r; }

    public double simulateMean(double lambda, int trials) {
        Random rand = new Random();
        long total = 0;
        for (int t = 0; t < trials; t++) {
            int count = 0;
            double limit = Math.exp(-lambda), prod = 1.0;
            do { count++; prod *= rand.nextDouble(); } while (prod > limit);
            total += count - 1;
        }
        return (double) total / trials;
    }

    public static void main(String[] args) {
        Problem20_PoissonDistribution sol = new Problem20_PoissonDistribution();
        System.out.println("P(X=3, λ=5): " + sol.pmf(3, 5));
        System.out.println("Simulated mean (λ=5): " + sol.simulateMean(5, 100000));
    }
}
