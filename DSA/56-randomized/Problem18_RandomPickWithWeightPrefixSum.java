import java.util.*;

public class Problem18_RandomPickWithWeightPrefixSum {
    // Detailed prefix sum approach with explanation
    int[] prefixSum;
    Random rand;

    public Problem18_RandomPickWithWeightPrefixSum(int[] w) {
        prefixSum = new int[w.length];
        prefixSum[0] = w[0];
        for (int i = 1; i < w.length; i++) prefixSum[i] = prefixSum[i-1] + w[i];
        rand = new Random();
    }

    public int pickIndex() {
        int target = rand.nextInt(prefixSum[prefixSum.length-1]) + 1;
        // Binary search for leftmost index where prefix >= target
        int lo = 0, hi = prefixSum.length - 1;
        while (lo < hi) {
            int mid = (lo + hi) / 2;
            if (prefixSum[mid] < target) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }

    public static void main(String[] args) {
        Problem18_RandomPickWithWeightPrefixSum sol = new Problem18_RandomPickWithWeightPrefixSum(new int[]{1,3,2});
        int[] counts = new int[3];
        for (int i = 0; i < 60000; i++) counts[sol.pickIndex()]++;
        System.out.println(Arrays.toString(counts)); // ~10000, 30000, 20000
    }
}
