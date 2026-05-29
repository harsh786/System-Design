import java.util.*;

public class Problem32_WeightedMedian {
    public double weightedMedian(int[] values, double[] weights) {
        Integer[] idx = new Integer[values.length];
        for (int i = 0; i < idx.length; i++) idx[i] = i;
        Arrays.sort(idx, (a, b) -> values[a] - values[b]);
        double totalWeight = 0;
        for (double w : weights) totalWeight += w;
        double cumWeight = 0;
        for (int i : idx) {
            cumWeight += weights[i];
            if (cumWeight >= totalWeight / 2) return values[i];
        }
        return values[idx[idx.length - 1]];
    }

    public static void main(String[] args) {
        Problem32_WeightedMedian sol = new Problem32_WeightedMedian();
        System.out.println(sol.weightedMedian(new int[]{1, 2, 3, 4, 5}, new double[]{0.15, 0.1, 0.2, 0.3, 0.25}));
    }
}
