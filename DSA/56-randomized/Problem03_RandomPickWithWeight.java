import java.util.*;

public class Problem03_RandomPickWithWeight {
    // Prefix sum + binary search for weighted random pick
    int[] prefix;
    int total;
    Random rand;

    public Problem03_RandomPickWithWeight(int[] w) {
        prefix = new int[w.length];
        prefix[0] = w[0];
        for (int i = 1; i < w.length; i++) prefix[i] = prefix[i-1] + w[i];
        total = prefix[w.length - 1];
        rand = new Random();
    }

    public int pickIndex() {
        int target = rand.nextInt(total) + 1;
        int lo = 0, hi = prefix.length - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (prefix[mid] < target) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }

    public static void main(String[] args) {
        Problem03_RandomPickWithWeight sol = new Problem03_RandomPickWithWeight(new int[]{1, 3});
        Map<Integer, Integer> freq = new HashMap<>();
        for (int i = 0; i < 10000; i++) freq.merge(sol.pickIndex(), 1, Integer::sum);
        System.out.println(freq); // ~25% index 0, ~75% index 1
    }
}
