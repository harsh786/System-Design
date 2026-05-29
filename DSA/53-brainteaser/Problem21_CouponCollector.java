import java.util.*;

public class Problem21_CouponCollector {
    // Expected draws to collect all n distinct coupons: n * H(n) where H(n) = harmonic number
    static double expected(int n) {
        double e = 0;
        for (int i = 1; i <= n; i++) e += (double) n / i;
        return e;
    }
    
    static double simulate(int n, int trials) {
        Random rand = new Random(42);
        long total = 0;
        for (int t = 0; t < trials; t++) {
            Set<Integer> collected = new HashSet<>();
            int draws = 0;
            while (collected.size() < n) { collected.add(rand.nextInt(n)); draws++; }
            total += draws;
        }
        return (double) total / trials;
    }
    
    public static void main(String[] args) {
        System.out.printf("n=10: expected=%.2f, simulated=%.2f%n", expected(10), simulate(10, 100000));
    }
}
