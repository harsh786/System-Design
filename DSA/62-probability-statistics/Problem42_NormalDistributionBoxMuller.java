import java.util.*;

public class Problem42_NormalDistributionBoxMuller {
    private Random rand = new Random();

    public double[] samplePair() {
        double u1 = rand.nextDouble(), u2 = rand.nextDouble();
        double r = Math.sqrt(-2 * Math.log(u1));
        double theta = 2 * Math.PI * u2;
        return new double[]{r * Math.cos(theta), r * Math.sin(theta)};
    }

    public double sample(double mean, double stddev) { return samplePair()[0] * stddev + mean; }

    public static void main(String[] args) {
        Problem42_NormalDistributionBoxMuller sol = new Problem42_NormalDistributionBoxMuller();
        double sum = 0, sum2 = 0; int n = 100000;
        for (int i = 0; i < n; i++) { double x = sol.sample(5, 2); sum += x; sum2 += x*x; }
        double mean = sum/n, var = sum2/n - mean*mean;
        System.out.printf("Mean: %.3f (exp 5), StdDev: %.3f (exp 2)%n", mean, Math.sqrt(var));
    }
}
