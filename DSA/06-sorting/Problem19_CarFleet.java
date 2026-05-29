import java.util.*;

/**
 * Problem 19: Car Fleet
 * 
 * Cars at different positions with different speeds heading to target. How many fleets arrive?
 * 
 * Approach: Sort by position descending. A car forms a new fleet if its time to reach target
 * is greater than the fleet ahead of it.
 * Time Complexity: O(n log n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Request batching - slower requests that started earlier absorb faster
 * ones behind them, forming "batches" that hit the backend together.
 */
public class Problem19_CarFleet {
    
    public int carFleet(int target, int[] position, int[] speed) {
        int n = position.length;
        if (n == 0) return 0;
        
        int[][] cars = new int[n][2];
        for (int i = 0; i < n; i++) cars[i] = new int[]{position[i], speed[i]};
        Arrays.sort(cars, (a, b) -> b[0] - a[0]); // sort by position desc
        
        int fleets = 1;
        double slowest = (double)(target - cars[0][0]) / cars[0][1];
        
        for (int i = 1; i < n; i++) {
            double time = (double)(target - cars[i][0]) / cars[i][1];
            if (time > slowest) {
                fleets++;
                slowest = time;
            }
        }
        return fleets;
    }
    
    public static void main(String[] args) {
        Problem19_CarFleet sol = new Problem19_CarFleet();
        
        System.out.println("Test 1: " + sol.carFleet(12, new int[]{10,8,0,5,3}, new int[]{2,4,1,1,3})); // 3
        System.out.println("Test 2: " + sol.carFleet(10, new int[]{3}, new int[]{3})); // 1
        System.out.println("Test 3: " + sol.carFleet(100, new int[]{0,2,4}, new int[]{4,2,1})); // 1
        System.out.println("Test 4: " + sol.carFleet(10, new int[]{}, new int[]{})); // 0
    }
}
