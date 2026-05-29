import java.util.*;

public class Problem39_ChiSquareTest {
    public double chiSquare(int[] observed, double[] expected) {
        double chi2 = 0;
        for (int i = 0; i < observed.length; i++) {
            double diff = observed[i] - expected[i];
            chi2 += diff * diff / expected[i];
        }
        return chi2;
    }

    public static void main(String[] args) {
        Problem39_ChiSquareTest sol = new Problem39_ChiSquareTest();
        // Test fairness of a 6-sided die with 600 rolls
        int[] observed = {90, 110, 95, 105, 100, 100};
        double[] expected = {100, 100, 100, 100, 100, 100};
        double chi2 = sol.chiSquare(observed, expected);
        System.out.printf("Chi-square: %.4f (critical at 0.05 with df=5: 11.07)%n", chi2);
        System.out.println("Fair? " + (chi2 < 11.07));
    }
}
