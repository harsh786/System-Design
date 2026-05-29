/**
 * Problem 28: Plates Between Candles (LeetCode 2055)
 * 
 * Pattern: Prefix sum of plates + precomputed nearest candle left/right
 * 
 * Time: O(n + q), Space: O(n)
 * 
 * Production Analogy: Counting items between delimiters in log parsing—
 * e.g., counting fields between pipe characters in fixed-format logs.
 */
import java.util.Arrays;

public class Problem28_PlatesBetweenCandles {

    public static int[] platesBetweenCandles(String s, int[][] queries) {
        int n = s.length();
        int[] prefixPlates = new int[n + 1];
        int[] nearestLeft = new int[n], nearestRight = new int[n];

        // Prefix sum of plates
        for (int i = 0; i < n; i++)
            prefixPlates[i + 1] = prefixPlates[i] + (s.charAt(i) == '*' ? 1 : 0);

        // Nearest candle to the left
        int last = -1;
        for (int i = 0; i < n; i++) {
            if (s.charAt(i) == '|') last = i;
            nearestLeft[i] = last;
        }
        // Nearest candle to the right
        last = -1;
        for (int i = n - 1; i >= 0; i--) {
            if (s.charAt(i) == '|') last = i;
            nearestRight[i] = last;
        }

        int[] result = new int[queries.length];
        for (int i = 0; i < queries.length; i++) {
            int l = nearestRight[queries[i][0]];
            int r = nearestLeft[queries[i][1]];
            if (l == -1 || r == -1 || l >= r) result[i] = 0;
            else result[i] = prefixPlates[r + 1] - prefixPlates[l];
        }
        return result;
    }

    public static void main(String[] args) {
        assert Arrays.equals(
            platesBetweenCandles("**|**|***|", new int[][]{{2,5},{5,9}}),
            new int[]{2, 3});
        assert Arrays.equals(
            platesBetweenCandles("***|**|*****|**||**|*", new int[][]{{1,17},{4,5},{14,17},{5,11},{15,16}}),
            new int[]{9, 0, 0, 0, 0});
        System.out.println("All tests passed!");
    }
}
