import java.util.*;

/**
 * Problem 36: Minimum Number of Refueling Stops (LeetCode 871)
 * 
 * Approach: Greedy with max-heap. Pass all reachable stations, if stuck,
 * refuel from the station with most fuel (from heap).
 * 
 * Time Complexity: O(N log N)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Resource budgeting - deciding which cache/buffer to expand
 * when running low, always picking the one offering maximum capacity boost.
 */
public class Problem36_MinRefuelingStops {
    
    public int minRefuelStops(int target, int startFuel, int[][] stations) {
        PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
        int fuel = startFuel, stops = 0, i = 0;
        
        while (fuel < target) {
            while (i < stations.length && stations[i][0] <= fuel) {
                maxHeap.offer(stations[i][1]);
                i++;
            }
            if (maxHeap.isEmpty()) return -1;
            fuel += maxHeap.poll();
            stops++;
        }
        return stops;
    }
    
    public static void main(String[] args) {
        Problem36_MinRefuelingStops sol = new Problem36_MinRefuelingStops();
        System.out.println(sol.minRefuelStops(100, 10, new int[][]{{10,60},{20,30},{30,30},{60,40}})); // 2
        System.out.println(sol.minRefuelStops(1, 1, new int[][]{})); // 0
        System.out.println(sol.minRefuelStops(100, 1, new int[][]{{10,100}})); // -1
    }
}
