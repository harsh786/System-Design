import java.util.*;

public class Problem40_TDigestQuantileEstimation {
    // T-Digest (simplified): Cluster-based quantile estimation for streams.
    // Simplified version using sorted centroids.
    
    static class Centroid implements Comparable<Centroid> {
        double mean;
        int count;
        Centroid(double m, int c) { mean = m; count = c; }
        public int compareTo(Centroid o) { return Double.compare(mean, o.mean); }
    }
    
    List<Centroid> centroids = new ArrayList<>();
    int maxCentroids;
    int totalCount = 0;
    
    public Problem40_TDigestQuantileEstimation() { this.maxCentroids = 100; }
    
    public void add(double value) {
        centroids.add(new Centroid(value, 1));
        totalCount++;
        if (centroids.size() > maxCentroids * 2) compress();
    }
    
    private void compress() {
        Collections.sort(centroids);
        List<Centroid> merged = new ArrayList<>();
        merged.add(centroids.get(0));
        for (int i = 1; i < centroids.size(); i++) {
            Centroid last = merged.get(merged.size() - 1);
            if (last.count + centroids.get(i).count <= totalCount / maxCentroids + 1) {
                double newMean = (last.mean * last.count + centroids.get(i).mean * centroids.get(i).count)
                    / (last.count + centroids.get(i).count);
                last.mean = newMean;
                last.count += centroids.get(i).count;
            } else {
                merged.add(centroids.get(i));
            }
        }
        centroids = merged;
    }
    
    public double quantile(double q) {
        compress();
        int target = (int)(q * totalCount);
        int cumulative = 0;
        for (Centroid c : centroids) {
            cumulative += c.count;
            if (cumulative >= target) return c.mean;
        }
        return centroids.get(centroids.size()-1).mean;
    }
    
    public static void main(String[] args) {
        Problem40_TDigestQuantileEstimation td = new Problem40_TDigestQuantileEstimation();
        Random rand = new Random(0);
        for (int i = 0; i < 10000; i++) td.add(rand.nextGaussian() * 10 + 50);
        System.out.printf("P50: %.1f, P90: %.1f, P99: %.1f%n",
            td.quantile(0.5), td.quantile(0.9), td.quantile(0.99));
    }
}
