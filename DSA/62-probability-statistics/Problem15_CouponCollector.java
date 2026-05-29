import java.util.*;

public class Problem15_CouponCollector {
    public double simulate(int n, int trials) {
        Random rand = new Random();
        long total = 0;
        for (int t = 0; t < trials; t++) {
            Set<Integer> collected = new HashSet<>();
            int steps = 0;
            while (collected.size() < n) { collected.add(rand.nextInt(n)); steps++; }
            total += steps;
        }
        return (double) total / trials;
    }

    public static void main(String[] args) {
        Problem15_CouponCollector sol = new Problem15_CouponCollector();
        System.out.println("Expected draws for 10 coupons: " + sol.simulate(10, 100000));
        // Theoretical: ~29.29 (10 * H_10)
    }
}
