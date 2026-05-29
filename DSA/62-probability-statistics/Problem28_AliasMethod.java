import java.util.*;

public class Problem28_AliasMethod {
    private int[] alias;
    private double[] prob;
    private Random rand = new Random();

    public Problem28_AliasMethod(double[] weights) {
        int n = weights.length;
        alias = new int[n];
        prob = new double[n];
        double total = 0;
        for (double w : weights) total += w;
        double[] scaled = new double[n];
        for (int i = 0; i < n; i++) scaled[i] = weights[i] * n / total;
        Deque<Integer> small = new ArrayDeque<>(), large = new ArrayDeque<>();
        for (int i = 0; i < n; i++) { if (scaled[i] < 1) small.push(i); else large.push(i); }
        while (!small.isEmpty() && !large.isEmpty()) {
            int s = small.pop(), l = large.pop();
            prob[s] = scaled[s]; alias[s] = l;
            scaled[l] -= (1 - scaled[s]);
            if (scaled[l] < 1) small.push(l); else large.push(l);
        }
        while (!large.isEmpty()) prob[large.pop()] = 1;
        while (!small.isEmpty()) prob[small.pop()] = 1;
    }

    public int sample() {
        int i = rand.nextInt(prob.length);
        return rand.nextDouble() < prob[i] ? i : alias[i];
    }

    public static void main(String[] args) {
        Problem28_AliasMethod sol = new Problem28_AliasMethod(new double[]{1, 2, 3, 4});
        int[] freq = new int[4];
        for (int i = 0; i < 100000; i++) freq[sol.sample()]++;
        System.out.println(Arrays.toString(freq));
    }
}
