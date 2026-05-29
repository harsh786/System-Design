/**
 * Problem: Robot Room Cleaner (LeetCode 489)
 * Approach: DFS with backtracking; robot interface simulation
 * Complexity: O(cells) time, O(cells) space
 * Production Analogy: Autonomous agent exploration with limited sensor input
 */
import java.util.*;
public class Problem39_RobotRoomCleaner {
    // Simulated Robot interface
    interface Robot {
        boolean move(); void turnLeft(); void turnRight(); void clean();
    }
    int[][] dirs = {{-1,0},{0,1},{1,0},{0,-1}};
    Set<String> visited = new HashSet<>();

    public void cleanRoom(Robot robot) { dfs(robot, 0, 0, 0); }
    void dfs(Robot robot, int r, int c, int d) {
        visited.add(r+","+c); robot.clean();
        for (int i = 0; i < 4; i++) {
            int nd = (d+i)%4, nr = r+dirs[nd][0], nc = c+dirs[nd][1];
            if (!visited.contains(nr+","+nc) && robot.move()) {
                dfs(robot, nr, nc, nd);
                robot.turnRight(); robot.turnRight(); robot.move();
                robot.turnRight(); robot.turnRight();
            }
            robot.turnRight();
        }
    }
    public static void main(String[] args) {
        System.out.println("Robot Room Cleaner - requires Robot interface for full execution");
    }
}
