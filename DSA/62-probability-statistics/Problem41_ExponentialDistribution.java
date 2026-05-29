import java.util.*;

public class Problem41_ExponentialDistribution {
    public double pdf(double x, double lambda) { return x < 0 ? 0 : lambda * Math.exp(-lambda * x); }
    public double cdf(double x, double lambda) { return x < 0 ? 0 : 1 - Math.exp(-lambda * x); }
    public double sample(double lambda) { return -Math.log(1 - new Random().nextDouble()) / lambda; }

    public static void main(String[] args) {
        Problem41_ExponentialDistribution sol = new Problem41_ExponentialDistribution();
        double sum = 0; int n = 100000;
        for (int i = 0; i < n; i++) sum += sol.sample(0.5);
        System.out.printf("Mean (expected 2.0): %.4f%n", sum/n);
    }
}
