import java.util.*;

/**
 * Problem 41: Russian Doll Envelopes
 * 
 * Find max number of envelopes you can nest (both width and height must be strictly larger).
 * 
 * Approach: Sort by width ascending, height descending (for same width).
 * Then LIS on heights using binary search.
 * 
 * Time: O(n log n), Space: O(n)
 * 
 * Production Analogy: Finding the longest chain of compatible API versions
 * where each subsequent version extends capabilities in all dimensions.
 */
public class Problem41_RussianDollEnvelopes {
    public static int maxEnvelopes(int[][] envelopes) {
        // Sort: width ascending, height descending for same width
        Arrays.sort(envelopes, (a, b) -> a[0] == b[0] ? b[1] - a[1] : a[0] - b[0]);
        
        // LIS on heights
        List<Integer> tails = new ArrayList<>();
        for (int[] env : envelopes) {
            int h = env[1];
            int lo = 0, hi = tails.size();
            while (lo < hi) {
                int mid = lo + (hi - lo) / 2;
                if (tails.get(mid) < h) lo = mid + 1;
                else hi = mid;
            }
            if (lo == tails.size()) tails.add(h);
            else tails.set(lo, h);
        }
        return tails.size();
    }

    public static void main(String[] args) {
        System.out.println(maxEnvelopes(new int[][]{{5,4},{6,4},{6,7},{2,3}})); // 3
        System.out.println(maxEnvelopes(new int[][]{{1,1},{1,1},{1,1}}));        // 1
        System.out.println(maxEnvelopes(new int[][]{{1,1}}));                    // 1
    }
}
