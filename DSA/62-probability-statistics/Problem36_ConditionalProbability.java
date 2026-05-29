import java.util.*;

public class Problem36_ConditionalProbability {
    /* P(A|B) = P(A∩B)/P(B) - simulate with dice example */
    public double simulate(int trials) {
        Random rand = new Random();
        int countB = 0, countAB = 0;
        for (int t = 0; t < trials; t++) {
            int d1 = rand.nextInt(6)+1, d2 = rand.nextInt(6)+1;
            int sum = d1 + d2;
            if (sum >= 8) { countB++; if (d1 == 6 || d2 == 6) countAB++; } // P(at least one 6 | sum>=8)
        }
        return (double) countAB / countB;
    }

    public static void main(String[] args) {
        Problem36_ConditionalProbability sol = new Problem36_ConditionalProbability();
        System.out.printf("P(at least one 6 | sum>=8): %.4f%n", sol.simulate(1000000));
    }
}
