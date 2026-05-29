import java.util.*;

/**
 * Problem: Race Car
 * Minimum instructions (A=accelerate, R=reverse) to reach target position.
 *
 * Approach: BFS on state (position, speed)
 *
 * Time Complexity: O(target * log(target))
 * Space Complexity: O(target * log(target))
 *
 * Production Analogy: Minimum control signals to reach target throughput.
 */
public class Problem23_RaceCar {

    public int racecar(int target) {
        Queue<int[]> q = new LinkedList<>();
        q.offer(new int[]{0, 1}); // position, speed
        Set<String> visited = new HashSet<>();
        visited.add("0,1");
        int steps = 0;

        while (!q.isEmpty()) {
            int size = q.size();
            for (int i = 0; i < size; i++) {
                int[] cur = q.poll();
                int pos = cur[0], speed = cur[1];
                // Accelerate
                int npos = pos + speed, nspeed = speed * 2;
                if (npos == target) return steps + 1;
                String key = npos + "," + nspeed;
                if (npos > 0 && npos < 2 * target && visited.add(key))
                    q.offer(new int[]{npos, nspeed});
                // Reverse
                nspeed = speed > 0 ? -1 : 1;
                key = pos + "," + nspeed;
                if (visited.add(key)) q.offer(new int[]{pos, nspeed});
            }
            steps++;
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem23_RaceCar solver = new Problem23_RaceCar();
        System.out.println(solver.racecar(6)); // 5
    }
}
