import java.util.*;

/**
 * Problem: Race Car (LeetCode 818)
 * Approach: BFS on state (position, speed), instructions A (accelerate) and R (reverse)
 * Time: O(target * log(target)), Space: O(target * log(target))
 * Production Analogy: Minimum instructions to reach target state in control systems
 */
public class Problem44_RaceCar {
    public int racecar(int target) {
        Queue<int[]> q = new LinkedList<>(); // [position, speed]
        q.offer(new int[]{0, 1});
        Set<String> visited = new HashSet<>();
        visited.add("0,1");
        int steps = 0;
        while (!q.isEmpty()) {
            int size = q.size();
            for (int i = 0; i < size; i++) {
                int[] curr = q.poll();
                int pos = curr[0], speed = curr[1];
                // Accelerate
                int newPos = pos + speed, newSpeed = speed * 2;
                if (newPos == target) return steps + 1;
                String key = newPos + "," + newSpeed;
                if (newPos > 0 && newPos < 2 * target && !visited.contains(key)) {
                    visited.add(key); q.offer(new int[]{newPos, newSpeed});
                }
                // Reverse
                newSpeed = speed > 0 ? -1 : 1;
                key = pos + "," + newSpeed;
                if (!visited.contains(key)) { visited.add(key); q.offer(new int[]{pos, newSpeed}); }
            }
            steps++;
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println(new Problem44_RaceCar().racecar(3)); // 2
        System.out.println(new Problem44_RaceCar().racecar(6)); // 5
    }
}
