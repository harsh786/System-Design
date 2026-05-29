import java.util.*;

public class Problem20_BirthdayParadox {
    // Probability of collision with n items in m slots
    static double probCollision(int n, int m) {
        double prob = 1.0;
        for (int i = 0; i < n; i++) prob *= (double)(m - i) / m;
        return 1 - prob;
    }
    
    // Simulate
    static double simulate(int n, int m, int trials) {
        Random rand = new Random(42);
        int collisions = 0;
        for (int t = 0; t < trials; t++) {
            Set<Integer> seen = new HashSet<>();
            boolean found = false;
            for (int i = 0; i < n; i++) {
                int v = rand.nextInt(m);
                if (!seen.add(v)) { found = true; break; }
            }
            if (found) collisions++;
        }
        return (double) collisions / trials;
    }
    
    public static void main(String[] args) {
        System.out.printf("23 people, 365 days: %.4f%n", probCollision(23, 365)); // ~0.5073
        System.out.printf("Simulated: %.4f%n", simulate(23, 365, 100000));
    }
}
