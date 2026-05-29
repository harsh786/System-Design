import java.util.*;

public class Problem40_HypergeometricDistribution {
    public double pmf(int N, int K, int n, int k) {
        return comb(K,k) * comb(N-K, n-k) / comb(N, n);
    }

    private double comb(int n, int k) {
        if (k < 0 || k > n) return 0;
        if (k > n-k) k = n-k;
        double r = 1;
        for (int i = 0; i < k; i++) r = r * (n-i) / (i+1);
        return r;
    }

    public static void main(String[] args) {
        Problem40_HypergeometricDistribution sol = new Problem40_HypergeometricDistribution();
        // Deck of 52, 4 aces, draw 5 cards, P(exactly 2 aces)
        System.out.printf("P(2 aces in 5 cards): %.6f%n", sol.pmf(52, 4, 5, 2));
    }
}
