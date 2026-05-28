/**
 * Problem 34: Gas Station
 * Circular route with gas stations. Find starting station to complete circuit.
 * 
 * Production Analogy: Like finding the optimal starting point in a circular pipeline
 * where each stage has production and consumption - find where surplus sustains the loop.
 * 
 * O(n) time, O(1) space - if total gas >= total cost, solution exists; track deficit
 */
public class Problem34_GasStation {

    public static int canCompleteCircuit(int[] gas, int[] cost) {
        int total = 0, tank = 0, start = 0;
        for (int i = 0; i < gas.length; i++) {
            int diff = gas[i] - cost[i];
            total += diff;
            tank += diff;
            if (tank < 0) { start = i + 1; tank = 0; }
        }
        return total >= 0 ? start : -1;
    }

    public static void main(String[] args) {
        System.out.println(canCompleteCircuit(new int[]{1,2,3,4,5}, new int[]{3,4,5,1,2})); // 3
        System.out.println(canCompleteCircuit(new int[]{2,3,4}, new int[]{3,4,3}));          // -1
    }
}
