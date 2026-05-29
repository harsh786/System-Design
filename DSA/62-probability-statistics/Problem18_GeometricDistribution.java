import java.util.*;

public class Problem18_GeometricDistribution {
    public double expectedTrials(double p) { return 1.0 / p; }

    public double simulate(double p, int trials) {
        Random rand = new Random();
        long totalSteps = 0;
        for (int t = 0; t < trials; t++) {
            int steps = 0;
            while (rand.nextDouble() >= p) steps++;
            totalSteps += steps + 1;
        }
        return (double) totalSteps / trials;
    }

    public static void main(String[] args) {
        Problem18_GeometricDistribution sol = new Problem18_GeometricDistribution();
        System.out.println("Expected (p=0.2): " + sol.expectedTrials(0.2));
        System.out.println("Simulated: " + sol.simulate(0.2, 100000));
    }
}
