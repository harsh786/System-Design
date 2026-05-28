import java.util.*;

/**
 * Problem 5: Car Fleet (LeetCode 853)
 * 
 * N cars heading to a target. A car fleet is formed when a faster car catches up.
 * Return the number of car fleets arriving at destination.
 * 
 * Approach: Sort by position descending. Use stack to track fleet times.
 * If current car takes longer than stack top, it forms a new fleet.
 * Time Complexity: O(n log n) for sorting
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like batch processing where faster jobs merge into slower preceding batches.
 */
public class Problem05_CarFleet {

    public static int carFleet(int target, int[] position, int[] speed) {
        int n = position.length;
        double[][] cars = new double[n][2];
        for (int i = 0; i < n; i++) {
            cars[i][0] = position[i];
            cars[i][1] = (double)(target - position[i]) / speed[i];
        }
        Arrays.sort(cars, (a, b) -> Double.compare(b[0], a[0])); // sort by position desc
        
        int fleets = 0;
        double maxTime = 0;
        for (double[] car : cars) {
            if (car[1] > maxTime) {
                maxTime = car[1];
                fleets++;
            }
        }
        return fleets;
    }

    public static void main(String[] args) {
        System.out.println(carFleet(12, new int[]{10,8,0,5,3}, new int[]{2,4,1,1,3})); // 3
        System.out.println(carFleet(10, new int[]{3}, new int[]{3})); // 1
        System.out.println(carFleet(100, new int[]{0,2,4}, new int[]{4,2,1})); // 1
    }
}
