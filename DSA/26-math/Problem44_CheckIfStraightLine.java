/**
 * Problem 44: Check If It Is a Straight Line
 * Given coordinates, check if they all lie on a single straight line.
 *
 * Approach: Cross product. (y2-y1)*(x3-x1) == (y3-y1)*(x2-x1) for all points.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like validating linear interpolation assumptions in
 * time-series data before applying linear regression.
 */
public class Problem44_CheckIfStraightLine {

    public static boolean checkStraightLine(int[][] coordinates) {
        int dx = coordinates[1][0] - coordinates[0][0];
        int dy = coordinates[1][1] - coordinates[0][1];

        for (int i = 2; i < coordinates.length; i++) {
            int dx2 = coordinates[i][0] - coordinates[0][0];
            int dy2 = coordinates[i][1] - coordinates[0][1];
            if ((long) dy * dx2 != (long) dx * dy2) return false;
        }
        return true;
    }

    public static void main(String[] args) {
        System.out.println(checkStraightLine(new int[][]{{1,2},{2,3},{3,4},{4,5}})); // true
        System.out.println(checkStraightLine(new int[][]{{1,1},{2,2},{3,4},{4,5}})); // false
    }
}
