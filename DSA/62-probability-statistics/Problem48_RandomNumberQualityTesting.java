import java.util.*;

public class Problem48_RandomNumberQualityTesting {
    /* Chi-square test for uniformity */
    public double chiSquareUniformity(int[] samples, int buckets) {
        int[] freq = new int[buckets];
        for (int s : samples) freq[s % buckets]++;
        double expected = (double)samples.length / buckets;
        double chi2 = 0;
        for (int f : freq) chi2 += (f - expected) * (f - expected) / expected;
        return chi2;
    }

    /* Runs test for randomness */
    public int runsTest(int[] samples) {
        int runs = 1;
        for (int i = 1; i < samples.length; i++) if (samples[i] != samples[i-1]) runs++;
        return runs;
    }

    public static void main(String[] args) {
        Problem48_RandomNumberQualityTesting sol = new Problem48_RandomNumberQualityTesting();
        Random rand = new Random(42);
        int[] samples = new int[10000];
        for (int i = 0; i < 10000; i++) samples[i] = rand.nextInt(100);
        System.out.printf("Chi-square (10 buckets): %.2f (critical ~16.92 for df=9)%n", sol.chiSquareUniformity(samples, 10));
    }
}
