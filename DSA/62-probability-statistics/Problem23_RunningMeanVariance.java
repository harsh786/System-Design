import java.util.*;

public class Problem23_RunningMeanVariance {
    private long count = 0;
    private double mean = 0, m2 = 0;

    public void add(double x) { count++; double d = x - mean; mean += d/count; m2 += d*(x-mean); }
    public double mean() { return mean; }
    public double variance() { return count > 1 ? m2/(count-1) : 0; }
    public double stddev() { return Math.sqrt(variance()); }

    public static void main(String[] args) {
        Problem23_RunningMeanVariance sol = new Problem23_RunningMeanVariance();
        Random r = new Random(42);
        for (int i = 0; i < 1000; i++) sol.add(r.nextGaussian() * 2 + 5);
        System.out.printf("Mean: %.3f, StdDev: %.3f%n", sol.mean(), sol.stddev());
    }
}
