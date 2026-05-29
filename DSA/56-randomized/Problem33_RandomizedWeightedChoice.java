import java.util.*;

public class Problem33_RandomizedWeightedChoice {
    // Alias method for O(1) weighted random selection after O(n) setup
    int[] alias;
    double[] prob;
    Random rand = new Random();

    public Problem33_RandomizedWeightedChoice(double[] weights) {
        int n = weights.length;
        alias = new int[n]; prob = new double[n];
        double sum = 0; for (double w : weights) sum += w;
        double[] norm = new double[n];
        for (int i = 0; i < n; i++) norm[i] = weights[i] * n / sum;
        Deque<Integer> small = new ArrayDeque<>(), large = new ArrayDeque<>();
        for (int i = 0; i < n; i++) { if (norm[i] < 1) small.push(i); else large.push(i); }
        while (!small.isEmpty() && !large.isEmpty()) {
            int s = small.pop(), l = large.pop();
            prob[s] = norm[s]; alias[s] = l;
            norm[l] -= (1 - norm[s]);
            if (norm[l] < 1) small.push(l); else large.push(l);
        }
        while (!large.isEmpty()) prob[large.pop()] = 1;
        while (!small.isEmpty()) prob[small.pop()] = 1;
    }

    public int pick() {
        int i = rand.nextInt(prob.length);
        return rand.nextDouble() < prob[i] ? i : alias[i];
    }

    public static void main(String[] args) {
        Problem33_RandomizedWeightedChoice wc = new Problem33_RandomizedWeightedChoice(new double[]{1,2,3,4});
        int[] counts = new int[4];
        for (int i = 0; i < 100000; i++) counts[wc.pick()]++;
        System.out.println(Arrays.toString(counts));
    }
}
