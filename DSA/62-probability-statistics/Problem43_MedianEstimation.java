import java.util.*;

public class Problem43_MedianEstimation {
    public double estimateMedian(double[] samples) {
        double[] copy = samples.clone();
        Arrays.sort(copy);
        int n = copy.length;
        return n % 2 == 1 ? copy[n/2] : (copy[n/2-1]+copy[n/2])/2;
    }

    public double bootstrapMedianCI(double[] data, int bootstraps) {
        Random rand = new Random();
        double[] medians = new double[bootstraps];
        for (int b = 0; b < bootstraps; b++) {
            double[] sample = new double[data.length];
            for (int i = 0; i < data.length; i++) sample[i] = data[rand.nextInt(data.length)];
            medians[b] = estimateMedian(sample);
        }
        Arrays.sort(medians);
        System.out.printf("95%% CI for median: [%.3f, %.3f]%n", medians[(int)(0.025*bootstraps)], medians[(int)(0.975*bootstraps)]);
        return estimateMedian(data);
    }

    public static void main(String[] args) {
        Problem43_MedianEstimation sol = new Problem43_MedianEstimation();
        Random r = new Random(42);
        double[] data = new double[100];
        for (int i = 0; i < 100; i++) data[i] = r.nextGaussian() * 3 + 10;
        System.out.printf("Median: %.3f%n", sol.bootstrapMedianCI(data, 1000));
    }
}
