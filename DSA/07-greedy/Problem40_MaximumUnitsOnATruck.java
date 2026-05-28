/**
 * Problem 40: Maximum Units on a Truck (LeetCode 1710)
 *
 * Greedy Choice: Load boxes with most units per box first (fractional knapsack style).
 *
 * Time: O(n log n), Space: O(1)
 *
 * Production Analogy: Maximizing value loaded in a container with weight/count limit.
 */
import java.util.*;
public class Problem40_MaximumUnitsOnATruck {
    
    public static int maximumUnits(int[][] boxTypes, int truckSize) {
        Arrays.sort(boxTypes, (a, b) -> b[1] - a[1]);
        int units = 0;
        for (int[] box : boxTypes) {
            int take = Math.min(box[0], truckSize);
            units += take * box[1];
            truckSize -= take;
            if (truckSize == 0) break;
        }
        return units;
    }
    
    public static void main(String[] args) {
        System.out.println(maximumUnits(new int[][]{{1,3},{2,2},{3,1}}, 4));         // 8
        System.out.println(maximumUnits(new int[][]{{5,10},{2,5},{4,7},{3,9}}, 10)); // 91
    }
}
