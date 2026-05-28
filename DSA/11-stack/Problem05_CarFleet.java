import java.util.*;

/**
 * Problem 5: Car Fleet (LeetCode 853)
 * 
 * N cars heading to a target. Each car has position and speed.
 * A car can't pass another; it joins a fleet. Return number of fleets.
 * 
 * Approach: Sort cars by position descending. Calculate time to reach target.
 * Use stack: if current car takes longer than top of stack, it forms a new fleet.
 * 
 * Time Complexity: O(n log n) for sorting
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like request batching in message queues - slower requests
 * ahead cause faster ones behind to "merge" into the same batch/fleet.
 */
public class Problem05_CarFleet {

    public static int carFleet(int target, int[] position, int[] speed) {
        int n = position.length;
        if (n == 0) return 0;
        int[][] cars = new int[n][2];
        for (int i = 0; i < n; i++) {
            cars[i][0] = position[i];
            cars[i][1] = speed[i];
        }
        Arrays.sort(cars, (a, b) -> b[0] - a[0]); // sort by position desc
        
        Deque<Double> stack = new ArrayDeque<>();
        for (int[] car : cars) {
            double time = (double)(target - car[0]) / car[1];
            if (stack.isEmpty() || time > stack.peek()) {
                stack.push(time);
            }
        }
        return stack.size();
    }

    public static void main(String[] args) {
        System.out.println(carFleet(12, new int[]{10,8,0,5,3}, new int[]{2,4,1,1,3})); // 3
        System.out.println(carFleet(10, new int[]{3}, new int[]{3})); // 1
        System.out.println(carFleet(100, new int[]{0,2,4}, new int[]{4,2,1})); // 1
    }
}
