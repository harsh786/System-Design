import java.util.*;

public class Problem19_BinomialDistribution {
    public double pmf(int n, int k, double p) {
        return comb(n, k) * Math.pow(p, k) * Math.pow(1 - p, n - k);
    }

    private double comb(int n, int k) {
        if (k > n - k) k = n - k;
        double result = 1;
        for (int i = 0; i < k; i++) result = result * (n - i) / (i + 1);
        return result;
    }

    public double simulate(int n, double p, int trials) {
        Random rand = new Random();
        double[] freq = new double[n + 1];
        for (int t = 0; t < trials; t++) {
            int successes = 0;
            for (int i = 0; i < n; i++) if (rand.nextDouble() < p) successes++;
            freq[successes]++;
        }
        // return mean
        double sum = 0;
        for (int i = 0; i <= n; i++) sum += i * freq[i];
        return sum / trials;
    }

    public static void main(String[] args) {
        Problem19_BinomialDistribution sol = new Problem19_BinomialDistribution();
        System.out.println("P(X=3) for B(10,0.5): " + sol.pmf(10, 3, 0.5));
        System.out.println("Simulated mean B(10,0.5): " + sol.simulate(10, 0.5, 100000));
    }
}
