import java.util.*;

/**
 * Problem 10: Minimum Number of Arrows to Burst Balloons
 * 
 * Balloons are represented as intervals. Find min arrows (vertical lines) to burst all.
 * 
 * Approach: Sort by end point. Greedily shoot at the end of the earliest-ending balloon.
 * Time Complexity: O(n log n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Minimum number of health checks needed to cover all service windows,
 * or minimum deployment windows to patch all affected services.
 */
public class Problem10_MinArrowsBurstBalloons {
    
    public int findMinArrowShots(int[][] points) {
        if (points.length == 0) return 0;
        Arrays.sort(points, (a, b) -> Integer.compare(a[1], b[1]));
        
        int arrows = 1;
        int arrowPos = points[0][1];
        
        for (int i = 1; i < points.length; i++) {
            if (points[i][0] > arrowPos) {
                arrows++;
                arrowPos = points[i][1];
            }
        }
        return arrows;
    }
    
    public static void main(String[] args) {
        Problem10_MinArrowsBurstBalloons sol = new Problem10_MinArrowsBurstBalloons();
        
        System.out.println("Test 1: " + sol.findMinArrowShots(new int[][]{{10,16},{2,8},{1,6},{7,12}})); // 2
        System.out.println("Test 2: " + sol.findMinArrowShots(new int[][]{{1,2},{3,4},{5,6},{7,8}})); // 4
        System.out.println("Test 3: " + sol.findMinArrowShots(new int[][]{{1,2},{2,3},{3,4},{4,5}})); // 2
        System.out.println("Test 4: " + sol.findMinArrowShots(new int[][]{{-2147483648,2147483647}})); // 1
    }
}
