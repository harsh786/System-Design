/**
 * Problem 7: Minimum Number of Arrows to Burst Balloons (LeetCode 452)
 *
 * Greedy Choice: Sort by end point, shoot at the end of the first balloon. Skip all overlapping.
 *
 * Time: O(n log n), Space: O(1)
 *
 * Production Analogy: Minimum number of health checks to cover all overlapping service windows.
 */
import java.util.*;
public class Problem07_MinArrowsBurstBalloons {
    
    public static int findMinArrowShots(int[][] points) {
        if (points.length == 0) return 0;
        Arrays.sort(points, (a, b) -> Integer.compare(a[1], b[1]));
        int arrows = 1;
        int end = points[0][1];
        for (int i = 1; i < points.length; i++) {
            if (points[i][0] > end) {
                arrows++;
                end = points[i][1];
            }
        }
        return arrows;
    }
    
    public static void main(String[] args) {
        System.out.println(findMinArrowShots(new int[][]{{10,16},{2,8},{1,6},{7,12}})); // 2
        System.out.println(findMinArrowShots(new int[][]{{1,2},{3,4},{5,6},{7,8}}));    // 4
        System.out.println(findMinArrowShots(new int[][]{{1,2},{2,3},{3,4},{4,5}}));    // 2
    }
}
