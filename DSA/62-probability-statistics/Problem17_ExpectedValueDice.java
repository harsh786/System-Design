import java.util.*;

public class Problem17_ExpectedValueDice {
    public double expectedValue(int sides) { return (sides + 1) / 2.0; }

    public double simulate(int sides, int rolls) {
        Random rand = new Random();
        long sum = 0;
        for (int i = 0; i < rolls; i++) sum += rand.nextInt(sides) + 1;
        return (double) sum / rolls;
    }

    public static void main(String[] args) {
        Problem17_ExpectedValueDice sol = new Problem17_ExpectedValueDice();
        System.out.println("Theoretical E[6-sided]: " + sol.expectedValue(6));
        System.out.println("Simulated E[6-sided]: " + sol.simulate(6, 1000000));
    }
}
