import java.util.*;

public class Problem44_BootstrapEstimation {
    public double[] bootstrapMeanCI(double[] data, int bootstraps, double confidence) {
        Random rand = new Random();
        double[] means = new double[bootstraps];
        for (int b = 0; b < bootstraps; b++) {
            double sum = 0;
            for (int i = 0; i < data.length; i++) sum += data[rand.nextInt(data.length)];
            means[b] = sum / data.length;
        }
        Arrays.sort(means);
        double alpha = (1 - confidence) / 2;
        return new double[]{means[(int)(alpha*bootstraps)], means[(int)((1-alpha)*bootstraps)]};
    }

    public static void main(String[] args) {
        Problem44_BootstrapEstimation sol = new Problem44_BootstrapEstimation();
        Random r = new Random(42);
        double[] data = new double[50];
        for (int i = 0; i < 50; i++) data[i] = r.nextGaussian() * 2 + 5;
        double[] ci = sol.bootstrapMeanCI(data, 10000, 0.95);
        System.out.printf("95%% CI for mean: [%.3f, %.3f]%n", ci[0], ci[1]);
    }
}
