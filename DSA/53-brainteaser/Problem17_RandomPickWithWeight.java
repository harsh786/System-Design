import java.util.*;

public class Problem17_RandomPickWithWeight {
    int[] prefix;
    int total;
    Random rand = new Random();
    
    Problem17_RandomPickWithWeight(int[] w) {
        prefix = new int[w.length];
        prefix[0] = w[0];
        for (int i = 1; i < w.length; i++) prefix[i] = prefix[i-1] + w[i];
        total = prefix[w.length - 1];
    }
    
    int pickIndex() {
        int target = rand.nextInt(total) + 1;
        int lo = 0, hi = prefix.length - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (prefix[mid] < target) lo = mid + 1; else hi = mid;
        }
        return lo;
    }
    
    public static void main(String[] args) {
        Problem17_RandomPickWithWeight sol = new Problem17_RandomPickWithWeight(new int[]{1, 3, 2});
        int[] count = new int[3];
        for (int i = 0; i < 60000; i++) count[sol.pickIndex()]++;
        System.out.println(Arrays.toString(count)); // ~10000, 30000, 20000
    }
}
