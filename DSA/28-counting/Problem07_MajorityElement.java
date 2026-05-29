/**
 * Problem: Majority Element (LeetCode 169)
 * Approach: Boyer-Moore Voting Algorithm
 * Complexity: O(n) time, O(1) space
 * Production Analogy: Leader election in distributed systems via voting
 */
public class Problem07_MajorityElement {
    public int majorityElement(int[] nums) {
        int candidate = 0, count = 0;
        for (int n : nums) {
            if (count == 0) candidate = n;
            count += (n == candidate) ? 1 : -1;
        }
        return candidate;
    }
    public static void main(String[] args) {
        System.out.println(new Problem07_MajorityElement().majorityElement(new int[]{2,2,1,1,1,2,2})); // 2
    }
}
