import java.util.*;

public class Problem49_LocalitySensitiveHashing {
    // LSH for cosine similarity using random hyperplanes
    private double[][] hyperplanes;
    private int numHashes;
    private int dim;
    private Map<String, List<double[]>> buckets = new HashMap<>();

    public Problem49_LocalitySensitiveHashing(int dim, int numHashes) {
        this.dim = dim;
        this.numHashes = numHashes;
        Random rand = new Random(42);
        hyperplanes = new double[numHashes][dim];
        for (int i = 0; i < numHashes; i++)
            for (int j = 0; j < dim; j++) hyperplanes[i][j] = rand.nextGaussian();
    }

    private String hash(double[] vector) {
        StringBuilder sb = new StringBuilder();
        for (double[] plane : hyperplanes) {
            double dot = 0;
            for (int i = 0; i < dim; i++) dot += vector[i] * plane[i];
            sb.append(dot >= 0 ? '1' : '0');
        }
        return sb.toString();
    }

    public void insert(double[] vector) {
        buckets.computeIfAbsent(hash(vector), k -> new ArrayList<>()).add(vector);
    }

    public List<double[]> querySimilar(double[] vector) {
        return buckets.getOrDefault(hash(vector), Collections.emptyList());
    }

    public static void main(String[] args) {
        Problem49_LocalitySensitiveHashing lsh = new Problem49_LocalitySensitiveHashing(3, 4);
        double[] v1 = {1, 2, 3}, v2 = {1.1, 2.1, 3.1}, v3 = {-1, -2, -3};
        lsh.insert(v1); lsh.insert(v2); lsh.insert(v3);
        List<double[]> similar = lsh.querySimilar(new double[]{1, 2, 2.9});
        System.out.println("Similar vectors found: " + similar.size());
    }
}
