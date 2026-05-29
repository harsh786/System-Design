import java.util.*;

public class Problem45_ConfidenceInterval {
    public double[] confidenceInterval(double[] data, double zCritical) {
        double mean = 0, n = data.length;
        for (double x : data) mean += x;
        mean /= n;
        double var = 0;
        for (double x : data) var += (x-mean)*(x-mean);
        var /= (n-1);
        double se = Math.sqrt(var / n);
        return new double[]{mean - zCritical*se, mean + zCritical*se};
    }

    public static void main(String[] args) {
        Problem45_ConfidenceInterval sol = new Problem45_ConfidenceInterval();
        double[] data = {4.2, 4.7, 5.1, 4.9, 5.3, 4.8, 5.0, 4.6, 5.2, 4.5};
        double[] ci = sol.confidenceInterval(data, 1.96); // 95%
        System.out.printf("95%% CI: [%.3f, %.3f]%n", ci[0], ci[1]);
    }
}
