import java.util.*;

/**
 * Problem 29: Robot Collisions (LeetCode 2751)
 * 
 * Robots at positions with health moving L or R. When they collide,
 * one with less health is removed, other loses 1 health. Return survivors.
 * 
 * Approach: Sort by position. Use stack for right-moving robots.
 * When left-moving robot arrives, resolve collisions with stack.
 * 
 * Time: O(n log n), Space: O(n)
 * 
 * Production Analogy: Service conflict resolution when opposing requests
 * meet at a shared resource.
 */
public class Problem29_RobotCollisions {
    
    public List<Integer> survivedRobotsHealths(int[] positions, int[] healths, String directions) {
        int n = positions.length;
        Integer[] indices = new Integer[n];
        for (int i = 0; i < n; i++) indices[i] = i;
        Arrays.sort(indices, (a, b) -> positions[a] - positions[b]);
        
        Deque<Integer> stack = new ArrayDeque<>(); // indices of right-moving robots
        int[] hp = healths.clone();
        boolean[] alive = new boolean[n];
        Arrays.fill(alive, true);
        
        for (int idx : indices) {
            if (directions.charAt(idx) == 'R') {
                stack.push(idx);
            } else {
                // Left-moving collides with right-moving in stack
                while (!stack.isEmpty() && alive[idx]) {
                    int right = stack.peek();
                    if (hp[right] < hp[idx]) {
                        alive[right] = false;
                        stack.pop();
                        hp[idx]--;
                    } else if (hp[right] == hp[idx]) {
                        alive[right] = false;
                        alive[idx] = false;
                        stack.pop();
                    } else {
                        alive[idx] = false;
                        hp[right]--;
                    }
                }
            }
        }
        
        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            if (alive[i]) result.add(hp[i]);
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem29_RobotCollisions sol = new Problem29_RobotCollisions();
        
        System.out.println(sol.survivedRobotsHealths(
            new int[]{5,4,3,2,1}, new int[]{2,17,9,15,10}, "RRRRL")); // [2,17,9,15,10] -> depends
        System.out.println(sol.survivedRobotsHealths(
            new int[]{3,5,2,6}, new int[]{10,10,15,12}, "RLRL")); // [14]
    }
}
