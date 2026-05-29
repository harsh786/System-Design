/**
 * Problem 17: Robot Bounded In Circle
 * Robot starts at origin facing north, executes instructions repeatedly.
 * Return true if robot stays in a bounded circle.
 *
 * Approach: After one pass, if robot is at origin OR not facing north, it's bounded.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like detecting if a scheduled job's state changes are
 * cyclical (will return to initial state) vs divergent.
 */
public class Problem17_RobotBoundedInCircle {

    public static boolean isRobotBounded(String instructions) {
        int x = 0, y = 0;
        int[][] dirs = {{0,1},{1,0},{0,-1},{-1,0}}; // N, E, S, W
        int d = 0; // facing north

        for (char c : instructions.toCharArray()) {
            if (c == 'G') { x += dirs[d][0]; y += dirs[d][1]; }
            else if (c == 'L') d = (d + 3) % 4;
            else d = (d + 1) % 4;
        }
        return (x == 0 && y == 0) || d != 0;
    }

    public static void main(String[] args) {
        System.out.println(isRobotBounded("GGLLGG")); // true
        System.out.println(isRobotBounded("GG"));     // false
        System.out.println(isRobotBounded("GL"));     // true
    }
}
