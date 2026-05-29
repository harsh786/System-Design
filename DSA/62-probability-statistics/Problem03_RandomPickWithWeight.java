import java.util.*;

public class Problem03_RandomPickWithWeight {
    private int[] prefix;
    private Random rand = new Random();

    public Problem03_RandomPickWithWeight(int[] w) {
        prefix = new int[w.length];
        prefix[0] = w[0];
        for (int i = 1; i < w.length; i++) prefix[i] = prefix[i-1] + w[i];
    }

    public int pickIndex() {
        int target = rand.nextInt(prefix[prefix.length - 1]) + 1;
        int lo = 0, hi = prefix.length - 1;
        while (lo < hi) { int mid = (lo + hi) / 2; if (prefix[mid] < target) lo = mid + 1; else hi = mid; }
        return lo;
    }

    public static void main(String[] args) {
        Problem03_RandomPickWithWeight sol = new Problem03_RandomPickWithWeight(new int[]{1, 3, 2});
        int[] freq = new int[3];
        for (int i = 0; i < 6000; i++) freq[sol.pickIndex()]++;
        System.out.println(Arrays.toString(freq));
    }
}
