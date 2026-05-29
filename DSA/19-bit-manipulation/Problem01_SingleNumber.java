/**
 * Problem 1: Single Number
 * Every element appears twice except one. Find that single one.
 * 
 * Approach: XOR all elements. a^a=0, a^0=a. Duplicates cancel out.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Detecting a single misconfigured server in pairs of replicas.
 */
public class Problem01_SingleNumber {
    public static int singleNumber(int[] nums) {
        int result = 0;
        for (int num : nums) {
            result ^= num; // XOR cancels duplicates
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(singleNumber(new int[]{2,2,1})); // 1
        System.out.println(singleNumber(new int[]{4,1,2,1,2})); // 4
        System.out.println(singleNumber(new int[]{1})); // 1
        System.out.println(singleNumber(new int[]{-1,-1,-2})); // -2
    }
}
