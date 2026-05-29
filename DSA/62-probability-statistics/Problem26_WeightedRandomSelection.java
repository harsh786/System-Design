import java.util.*;

public class Problem26_WeightedRandomSelection {
    public int select(double[] weights) {
        double total = 0;
        for (double w : weights) total += w;
        double r = new Random().nextDouble() * total;
        double cum = 0;
        for (int i = 0; i < weights.length; i++) { cum += weights[i]; if (cum > r) return i; }
        return weights.length - 1;
    }

    public static void main(String[] args) {
        Problem26_WeightedRandomSelection sol = new Problem26_WeightedRandomSelection();
        double[] weights = {1, 2, 3, 4};
        int[] freq = new int[4];
        for (int i = 0; i < 10000; i++) freq[sol.select(weights)]++;
        System.out.println(Arrays.toString(freq));
    }
}
