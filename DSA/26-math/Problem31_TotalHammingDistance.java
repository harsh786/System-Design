/**
 * Problem 31: Total Hamming Distance
 * Sum of Hamming distances between all pairs in array.
 *
 * Approach: For each bit position, count numbers with that bit set (c) and unset (n-c).
 * Contribution = c * (n-c).
 * Time Complexity: O(32 * n) = O(n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like computing total divergence across distributed replicas
 * for consistency metrics.
 */
public class Problem31_TotalHammingDistance {

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
