/**
 * Problem 45: Interval List Intersections
 * 
 * Find intersection of two sorted interval lists.
 * 
 * Approach: Two pointers, one per list. Compute overlap, advance the one ending earlier.
 * Time: O(m+n), Space: O(1) excluding output
 * 
 * Production Analogy: Like finding overlapping availability windows between
 * two calendars for meeting scheduling.
 */
import java.util.*;

public class Problem45_IntervalListIntersections {
    public static int[][] intervalIntersection(int[][] firstList, int[][] secondList) {
        List<int[]> result = new ArrayList<>();
        int i = 0, j = 0;
        while (i < firstList.length && j < secondList.length) {
            int lo = Math.max(firstList[i][0], secondList[j][0]);
            int hi = Math.min(firstList[i][1], secondList[j][1]);
            if (lo <= hi) result.add(new int[]{lo, hi});
            if (firstList[i][1] < secondList[j][1]) i++;
            else j++;
        }
        return result.toArray(new int[0][]);
    }

    public static void main(String[] args) {
        int[][] a = {{0,2},{5,10},{13,23},{24,25}};
        int[][] b = {{1,5},{8,12},{15,24},{25,26}};
        int[][] res = intervalIntersection(a, b);
        for (int[] r : res) System.out.print(Arrays.toString(r) + " ");
        // [1,2] [5,5] [8,10] [15,23] [24,24] [25,25]
        System.out.println();
    }
}
