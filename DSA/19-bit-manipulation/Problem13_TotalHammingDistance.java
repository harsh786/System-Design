/**
 * Problem 13: Total Hamming Distance
 * Sum of Hamming distances between all pairs.
 * 
 * Approach: For each bit position, count nums with 1. Contribution = count1 * count0.
 * Time: O(32n) = O(n), Space: O(1)
 * 
 * Production Analogy: Measuring total config divergence across a fleet of servers.
 */
public class Problem13_TotalHammingDistance {
    public static int totalHammingDistance(int[] nums) {
        int total = 0, n = nums.length;
        for (int bit = 0; bit < 32; bit++) {
            int ones = 0;
            for (int num : nums) {
                ones += (num >> bit) & 1;
            }
            total += ones * (n - ones);
        }
        return total;
    }

    public static void main(String[] args) {
        System.out.println(totalHammingDistance(new int[]{4, 14, 2})); // 6
        System.out.println(totalHammingDistance(new int[]{4, 14, 4})); // 4
    }
}
