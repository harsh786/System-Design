/**
 * Problem: Walking Robot Simulation (LeetCode 874)
 * Approach: Simulate step-by-step with obstacle set lookup
 * Complexity: O(n + k) time where k=total steps, O(obstacles) space
 * Production Analogy: Pathfinding with obstacle avoidance in autonomous systems
 */
import java.util.*;
public class Problem04_WalkingRobotSimulation {
    public int robotSim(int[] commands, int[][] obstacles) {
        Set<String> obs = new HashSet<>();
        for (int[] o : obstacles) obs.add(o[0]+","+o[1]);
        int[][] dirs = {{0,1},{1,0},{0,-1},{-1,0}};
        int x=0,y=0,d=0,max=0;
        for (int cmd : commands) {
            if (cmd==-2) d=(d+3)%4;
            else if (cmd==-1) d=(d+1)%4;
            else {
                for (int i=0; i<cmd; i++) {
                    int nx=x+dirs[d][0], ny=y+dirs[d][1];
                    if (obs.contains(nx+","+ny)) break;
                    x=nx; y=ny;
                    max=Math.max(max, x*x+y*y);
                }
            }
        }
        return max;
    }
    public static void main(String[] args) {
        System.out.println(new Problem04_WalkingRobotSimulation().robotSim(new int[]{4,-1,3}, new int[][]{})); // 25
    }
}
