import java.util.*;

public class Problem38_ABTestSignificance {
    public double zScore(int nA, int successA, int nB, int successB) {
        double pA = (double)successA/nA, pB = (double)successB/nB;
        double pPool = (double)(successA+successB)/(nA+nB);
        double se = Math.sqrt(pPool*(1-pPool)*(1.0/nA + 1.0/nB));
        return (pA - pB) / se;
    }

    public boolean isSignificant(int nA, int successA, int nB, int successB, double alpha) {
        double z = Math.abs(zScore(nA, successA, nB, successB));
        double zCritical = alpha == 0.05 ? 1.96 : 2.576; // 0.05 or 0.01
        return z > zCritical;
    }

    public static void main(String[] args) {
        Problem38_ABTestSignificance sol = new Problem38_ABTestSignificance();
        System.out.printf("Z-score: %.4f%n", sol.zScore(1000, 120, 1000, 100));
        System.out.println("Significant at 0.05? " + sol.isSignificant(1000, 120, 1000, 100, 0.05));
    }
}
