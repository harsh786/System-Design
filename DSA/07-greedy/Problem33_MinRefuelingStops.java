/**
 * Problem 33: Minimum Number of Refueling Stops (LeetCode 871)
 *
 * Greedy Choice: Drive as far as possible. When stuck, refuel at the station with most fuel passed.
 *
 * Time: O(n log n), Space: O(n)
 *
 * Production Analogy: Minimum cache refills on a CDN path, choosing largest cache at each hop.
 */
import java.util.*;
public class Problem33_MinRefuelingStops {
    
    public static int minRefuelStops(int target, int startFuel, int[][] stations) {
        PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
        int fuel = startFuel, stops = 0, idx = 0;
        while (fuel < target) {
            while (idx < stations.length && stations[idx][0] <= fuel)
                maxHeap.offer(stations[idx++][1]);
            if (maxHeap.isEmpty()) return -1;
            fuel += maxHeap.poll();
            stops++;
        }
        return stops;
    }
    
    public static void main(String[] args) {
        System.out.println(minRefuelStops(1, 1, new int[][]{}));                          // 0
        System.out.println(minRefuelStops(100, 1, new int[][]{{10,100}}));                // -1
        System.out.println(minRefuelStops(100, 10, new int[][]{{10,60},{20,30},{30,30},{60,40}})); // 2
    }
}
