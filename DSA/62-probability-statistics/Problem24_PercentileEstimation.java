import java.util.*;

public class Problem24_PercentileEstimation {
    /* Simplified T-Digest-like percentile estimation using sorted list of centroids */
    private List<double[]> centroids = new ArrayList<>(); // [mean, count]

    public void add(double x) {
        centroids.add(new double[]{x, 1});
        if (centroids.size() > 100) compress();
    }

    private void compress() {
        centroids.sort((a, b) -> Double.compare(a[0], b[0]));
        List<double[]> compressed = new ArrayList<>();
        double[] cur = centroids.get(0);
        for (int i = 1; i < centroids.size(); i++) {
            if (cur[1] + centroids.get(i)[1] <= 10) {
                cur[0] = (cur[0]*cur[1] + centroids.get(i)[0]*centroids.get(i)[1]) / (cur[1]+centroids.get(i)[1]);
                cur[1] += centroids.get(i)[1];
            } else { compressed.add(cur); cur = centroids.get(i); }
        }
        compressed.add(cur);
        centroids = compressed;
    }

    public double percentile(double p) {
        compress();
        double total = 0;
        for (double[] c : centroids) total += c[1];
        double target = p / 100.0 * total, cum = 0;
        for (double[] c : centroids) { cum += c[1]; if (cum >= target) return c[0]; }
        return centroids.get(centroids.size()-1)[0];
    }

    public static void main(String[] args) {
        Problem24_PercentileEstimation sol = new Problem24_PercentileEstimation();
        Random r = new Random(42);
        for (int i = 0; i < 10000; i++) sol.add(r.nextGaussian());
        System.out.printf("P50: %.3f, P95: %.3f, P99: %.3f%n", sol.percentile(50), sol.percentile(95), sol.percentile(99));
    }
}
