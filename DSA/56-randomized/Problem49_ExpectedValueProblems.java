import java.util.*;

public class Problem49_ExpectedValueProblems {
    static Random rand = new Random();

    // Expected #rolls to see all faces of a die (Coupon Collector)
    static double couponCollector(int n, int trials) {
        long total = 0;
        for (int t = 0; t < trials; t++) {
            Set<Integer> seen = new HashSet<>();
            int rolls = 0;
            while (seen.size() < n) { seen.add(rand.nextInt(n)); rolls++; }
            total += rolls;
        }
        return (double) total / trials;
    }

    // Expected #comparisons for randomized search
    static double expectedSearchCost(int n, int trials) {
        long total = 0;
        for (int t = 0; t < trials; t++) {
            int target = rand.nextInt(n);
            List<Integer> order = new ArrayList<>();
            for (int i = 0; i < n; i++) order.add(i);
            Collections.shuffle(order, rand);
            for (int i = 0; i < n; i++) { total++; if (order.get(i) == target) break; }
        }
        return (double) total / trials;
    }

    public static void main(String[] args) {
        System.out.printf("Coupon Collector (n=6): expected %.2f rolls (theory: %.2f)%n",
            couponCollector(6, 100000), 6*(1+1/2.0+1/3.0+1/4.0+1/5.0+1/6.0));
        System.out.printf("Random search (n=100): expected %.2f comparisons (theory: 50.5)%n",
            expectedSearchCost(100, 100000));
    }
}
