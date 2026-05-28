import java.util.*;

/**
 * Problem 40: Longest Increasing Subsequence (Binary Search approach)
 * 
 * Approach: Maintain a "tails" array where tails[i] = smallest tail element
 * for an increasing subsequence of length i+1. Binary search for insertion point.
 * 
 * Time: O(n log n), Space: O(n)
 * 
 * Production Analogy: Tracking the longest chain of monotonically increasing
 * deployment versions across dependent microservices.
 */
public class Problem40_LongestIncreasingSubsequence {
    public static int lengthOfLIS(int[] nums) {
        List<Integer> tails = new ArrayList<>();
        for (int num : nums) {
            int lo = 0, hi = tails.size();
            while (lo < hi) {
                int mid = lo + (hi - lo) / 2;
                if (tails.get(mid) < num) lo = mid + 1;
                else hi = mid;
            }
            if (lo == tails.size()) tails.add(num);
            else tails.set(lo, num);
        }
        return tails.size();
    }

    public static void main(String[] args) {
        System.out.println(lengthOfLIS(new int[]{10,9,2,5,3,7,101,18})); // 4
        System.out.println(lengthOfLIS(new int[]{0,1,0,3,2,3}));          // 4
        System.out.println(lengthOfLIS(new int[]{7,7,7,7,7}));            // 1
        System.out.println(lengthOfLIS(new int[]{1}));                     // 1
    }
}
