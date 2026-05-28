/**
 * Problem 29: Two City Scheduling (LeetCode 1029)
 *
 * Greedy Choice: Sort by cost difference (costA - costB). Send first half to A, rest to B.
 *
 * Time: O(n log n), Space: O(1)
 *
 * Production Analogy: Assigning workloads to two data centers minimizing total network cost.
 */
import java.util.*;
public class Problem29_TwoCityScheduling {
    
    public static int twoCitySchedCost(int[][] costs) {
        Arrays.sort(costs, (a, b) -> (a[0] - a[1]) - (b[0] - b[1]));
        int total = 0, n = costs.length / 2;
        for (int i = 0; i < n; i++) total += costs[i][0] + costs[i + n][1];
        return total;
    }
    
    public static void main(String[] args) {
        System.out.println(twoCitySchedCost(new int[][]{{10,20},{30,200},{400,50},{30,20}})); // 110
        System.out.println(twoCitySchedCost(new int[][]{{259,770},{448,54},{926,667},{184,139},{840,118},{577,469}})); // 1859
    }
}
