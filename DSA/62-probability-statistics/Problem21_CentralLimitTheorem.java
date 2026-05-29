import java.util.*;

public class Problem21_CentralLimitTheorem {
    public void demonstrate(int sampleSize, int numSamples) {
        Random rand = new Random();
        double[] means = new double[numSamples];
        for (int i = 0; i < numSamples; i++) {
            double sum = 0;
            for (int j = 0; j < sampleSize; j++) sum += rand.nextDouble(); // Uniform[0,1]
            means[i] = sum / sampleSize;
        }
        double mean = 0, var = 0;
        for (double m : means) mean += m;
        mean /= numSamples;
        for (double m : means) var += (m - mean) * (m - mean);
        var /= numSamples;
        System.out.printf("Sample mean of means: %.4f (expected 0.5)%n", mean);
        System.out.printf("Variance of means: %.6f (expected %.6f)%n", var, 1.0/(12*sampleSize));
    }

    public static void main(String[] args) {
        Problem21_CentralLimitTheorem sol = new Problem21_CentralLimitTheorem();
        sol.demonstrate(30, 10000);
    }
}
