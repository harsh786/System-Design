import java.util.*;

public class Problem13_WeightedReservoirSample {
    // A-Res algorithm: key = random^(1/weight), keep top-k keys
    public static int[] weightedReservoir(int[] items, double[] weights, int k) {
        Random rand = new Random();
        PriorityQueue<double[]> pq = new PriorityQueue<>((a,b) -> Double.compare(a[0], b[0]));
        for (int i = 0; i < items.length; i++) {
            double key = Math.pow(rand.nextDouble(), 1.0 / weights[i]);
            if (pq.size() < k) pq.offer(new double[]{key, i});
            else if (key > pq.peek()[0]) { pq.poll(); pq.offer(new double[]{key, i}); }
        }
        int[] result = new int[k];
        int idx = 0;
        for (double[] d : pq) result[idx++] = items[(int)d[1]];
        return result;
    }

    public static void main(String[] args) {
        int[] items = {0,1,2,3,4};
        double[] weights = {1,2,3,4,5};
        System.out.println(Arrays.toString(weightedReservoir(items, weights, 2)));
    }
}
