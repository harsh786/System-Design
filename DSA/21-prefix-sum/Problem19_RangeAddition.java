/**
 * Problem 19: Range Addition (LeetCode 370) - Difference Array
 * 
 * Pattern: For each update [start, end, val], do diff[start] += val, diff[end+1] -= val.
 * Final array is prefix sum of diff.
 * 
 * Time: O(n + k) where k = number of updates
 * Space: O(n)
 * 
 * Production Analogy: Applying bulk discount adjustments across product ranges
 * in an e-commerce pricing engine without updating each item individually.
 */
import java.util.Arrays;

public class Problem19_RangeAddition {

    public static int[] getModifiedArray(int length, int[][] updates) {
        int[] diff = new int[length];
        for (int[] u : updates) {
            diff[u[0]] += u[2];
            if (u[1] + 1 < length) diff[u[1] + 1] -= u[2];
        }
        for (int i = 1; i < length; i++)
            diff[i] += diff[i - 1];
        return diff;
    }

    public static void main(String[] args) {
        int[][] updates = {{1,3,2},{2,4,3},{0,2,-2}};
        assert Arrays.equals(getModifiedArray(5, updates), new int[]{-2, 0, 3, 5, 3});
        assert Arrays.equals(getModifiedArray(3, new int[][]{{0,2,1}}), new int[]{1,1,1});
        System.out.println("All tests passed!");
    }
}
