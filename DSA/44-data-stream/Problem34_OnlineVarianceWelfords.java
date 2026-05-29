import java.util.*;

public class Problem34_OnlineVarianceWelfords {
    // Welford's Online Algorithm for computing variance in a single pass.
    
    long count = 0;
    double mean = 0, m2 = 0;
    
    public void add(double value) {
        count++;
        double delta = value - mean;
        mean += delta / count;
        double delta2 = value - mean;
        m2 += delta * delta2;
    }
    
    public double getMean() { return mean; }
    public double getVariance() { return count < 2 ? 0 : m2 / (count - 1); }
    public double getStdDev() { return Math.sqrt(getVariance()); }
    
    public static void main(String[] args) {
        Problem34_OnlineVarianceWelfords sol = new Problem34_OnlineVarianceWelfords();
        double[] data = {2, 4, 4, 4, 5, 5, 7, 9};
        for (double d : data) sol.add(d);
        System.out.printf("Mean: %.2f, Variance: %.2f, StdDev: %.2f%n",
            sol.getMean(), sol.getVariance(), sol.getStdDev());
        // Mean: 5.00, Variance: 4.57, StdDev: 2.14
    }
}
