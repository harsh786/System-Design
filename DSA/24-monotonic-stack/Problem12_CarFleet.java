import java.util.*;

/**
 * Problem 12: Car Fleet (LeetCode 853)
 * 
 * Cars at different positions with different speeds heading to target.
 * A faster car behind a slower one forms a fleet. Count fleets.
 * 
 * Approach: Sort by position descending. Use stack to track fleet arrival times.
 * If a car arrives earlier/same as the one ahead, it merges (doesn't form new fleet).
 * 
 * Monotonic Invariant: Increasing stack of arrival times (each entry = one fleet).
 * 
 * Time: O(n log n), Space: O(n)
 * 
 * Production Analogy: Request batching - slower requests ahead cause faster ones
 * behind to queue up into a batch.
 */
public class Problem12_CarFleet {
    
    public int carFleet(int target, int[] position, int[] speed) {
        int n = position.length;
        int[][] cars = new int[n][2];
        for (int i = 0; i < n; i++) cars[i] = new int[]{position[i], speed[i]};
        Arrays.sort(cars, (a, b) -> b[0] - a[0]); // sort by position desc
        
        Deque<Double> stack = new ArrayDeque<>();
        for (int[] car : cars) {
            double time = (double)(target - car[0]) / car[1];
            if (stack.isEmpty() || time > stack.peek()) {
                stack.push(time);
            }
            // else: merges with fleet ahead
        }
        return stack.size();
    }
    
    public static void main(String[] args) {
        Problem12_CarFleet sol = new Problem12_CarFleet();
        
        System.out.println(sol.carFleet(12, new int[]{10,8,0,5,3}, new int[]{2,4,1,1,3})); // 3
        System.out.println(sol.carFleet(10, new int[]{3}, new int[]{3})); // 1
        System.out.println(sol.carFleet(100, new int[]{0,2,4}, new int[]{4,2,1})); // 1
    }
}
