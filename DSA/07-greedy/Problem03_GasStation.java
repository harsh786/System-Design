/**
 * Problem 3: Gas Station (LeetCode 134)
 *
 * Greedy Choice: If total gas >= total cost, a solution exists. Start from the point
 * after which the running tank never goes negative.
 * Exchange Argument: If starting at i fails at j, no start between i and j works.
 *
 * Time: O(n), Space: O(1)
 *
 * Production Analogy: Finding optimal data center to start a circular replication chain
 * where each hop has bandwidth cost and each node provides bandwidth.
 */
public class Problem03_GasStation {
    
    public static int canCompleteCircuit(int[] gas, int[] cost) {
        int totalTank = 0, currTank = 0, start = 0;
        for (int i = 0; i < gas.length; i++) {
            int diff = gas[i] - cost[i];
            totalTank += diff;
            currTank += diff;
            if (currTank < 0) {
                start = i + 1;
                currTank = 0;
            }
        }
        return totalTank >= 0 ? start : -1;
    }
    
    public static void main(String[] args) {
        System.out.println(canCompleteCircuit(new int[]{1,2,3,4,5}, new int[]{3,4,5,1,2})); // 3
        System.out.println(canCompleteCircuit(new int[]{2,3,4}, new int[]{3,4,3}));          // -1
        System.out.println(canCompleteCircuit(new int[]{5,1,2,3,4}, new int[]{4,4,1,5,1})); // 4
    }
}
