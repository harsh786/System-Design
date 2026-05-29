import java.util.*;

public class Problem30_MarkovChainSimulation {
    /* Simple 3-state Markov chain simulation */
    public int[] simulate(double[][] transition, int startState, int steps) {
        Random rand = new Random();
        int[] visits = new int[transition.length];
        int state = startState;
        for (int s = 0; s < steps; s++) {
            visits[state]++;
            double r = rand.nextDouble(), cum = 0;
            for (int j = 0; j < transition[state].length; j++) {
                cum += transition[state][j];
                if (r < cum) { state = j; break; }
            }
        }
        return visits;
    }

    public static void main(String[] args) {
        Problem30_MarkovChainSimulation sol = new Problem30_MarkovChainSimulation();
        double[][] T = {{0.7, 0.2, 0.1}, {0.3, 0.4, 0.3}, {0.2, 0.3, 0.5}};
        int[] visits = sol.simulate(T, 0, 100000);
        int total = 0; for (int v : visits) total += v;
        System.out.printf("Stationary dist: [%.3f, %.3f, %.3f]%n", (double)visits[0]/total, (double)visits[1]/total, (double)visits[2]/total);
    }
}
