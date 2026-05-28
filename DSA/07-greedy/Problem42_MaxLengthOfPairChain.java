/**
 * Problem 42: Maximum Length of Pair Chain (LeetCode 646)
 *
 * Greedy Choice: Sort by end, greedily pick non-overlapping pairs (same as activity selection).
 *
 * Time: O(n log n), Space: O(1)
 *
 * Production Analogy: Longest chain of non-overlapping scheduled jobs.
 */
import java.util.*;
public class Problem42_MaxLengthOfPairChain {
    
    public static int findLongestChain(int[][] pairs) {
        Arrays.sort(pairs, (a, b) -> a[1] - b[1]);
        int count = 1, end = pairs[0][1];
        for (int i = 1; i < pairs.length; i++) {
            if (pairs[i][0] > end) {
                count++;
                end = pairs[i][1];
            }
        }
        return count;
    }
    
    public static void main(String[] args) {
        System.out.println(findLongestChain(new int[][]{{1,2},{2,3},{3,4}}));     // 2
        System.out.println(findLongestChain(new int[][]{{1,2},{7,8},{4,5}}));     // 3
    }
}
