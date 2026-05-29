import java.util.*;

public class Problem22_WelfordsOnlineVariance {
    private int count = 0;
    private double mean = 0, m2 = 0;

    public void update(double x) {
        count++;
        double delta = x - mean;
        mean += delta / count;
        double delta2 = x - mean;
        m2 += delta * delta2;
    }

    public double getMean() { return mean; }
    public double getVariance() { return count < 2 ? 0 : m2 / (count - 1); }

    public static void main(String[] args) {
        Problem22_WelfordsOnlineVariance sol = new Problem22_WelfordsOnlineVariance();
        double[] data = {2, 4, 4, 4, 5, 5, 7, 9};
        for (double x : data) sol.update(x);
        System.out.printf("Mean: %.2f, Variance: %.2f%n", sol.getMean(), sol.getVariance());
    }
}
