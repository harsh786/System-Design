import java.util.*;

public class Problem34_NoisyBinarySearch {
    // Binary search where oracle lies with probability p
    static int[] arr = {1,2,3,4,5,6,7,8,9,10};
    static Random rand = new Random(42);
    static double lieProb = 0.2;
    
    static int noisyCompare(int idx, int target) {
        int truth = Integer.compare(arr[idx], target);
        if (rand.nextDouble() < lieProb) return -truth; // lie
        return truth;
    }
    
    static int noisyBinarySearch(int n, int target) {
        // Repeat queries and take majority
        double[] logProb = new double[n];
        int lo = 0, hi = n - 1;
        for (int iter = 0; iter < 50; iter++) {
            int mid = lo + (hi - lo) / 2;
            int res = noisyCompare(mid, target);
            if (res == 0) return mid;
            // Use majority voting with repeated queries
            int votes = 0;
            for (int r = 0; r < 5; r++) votes += noisyCompare(mid, target) < 0 ? -1 : 1;
            if (votes < 0) hi = mid - 1; else lo = mid + 1;
            if (lo > hi) break;
        }
        return lo < n && arr[lo] == target ? lo : -1;
    }
    
    public static void main(String[] args) {
        System.out.println("Noisy search for 7: " + noisyBinarySearch(10, 7));
    }
}
