import java.util.*;

public class Problem34_ExpectedTossesForHeads {
    public double expected(double p) { return 1.0 / p; }

    public double simulate(double p, int trials) {
        Random rand = new Random();
        long total = 0;
        for (int t = 0; t < trials; t++) { int c = 0; do { c++; } while (rand.nextDouble() >= p); total += c; }
        return (double) total / trials;
    }

    public static void main(String[] args) {
        Problem34_ExpectedTossesForHeads sol = new Problem34_ExpectedTossesForHeads();
        System.out.printf("Expected tosses (p=0.3): theory=%.2f sim=%.2f%n", sol.expected(0.3), sol.simulate(0.3, 100000));
    }
}
