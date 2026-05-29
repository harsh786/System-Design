/**
 * Problem 2: Single Number II
 * Every element appears three times except one. Find that single one.
 * 
 * Approach: Count bits at each position mod 3. The remaining bits form the answer.
 * Time: O(32n) = O(n), Space: O(1)
 * 
 * Production Analogy: Triple-replicated data store detecting a corrupted single replica.
 */
public class Problem02_SingleNumberII {
    public static int singleNumber(int[] nums) {
        int ones = 0, twos = 0;
        for (int num : nums) {
            // ones holds bits that appeared once (mod 3)
            // twos holds bits that appeared twice (mod 3)
            ones = (ones ^ num) & ~twos;
            twos = (twos ^ num) & ~ones;
        }
        return ones;
    }

    public static void main(String[] args) {
        System.out.println(singleNumber(new int[]{2,2,3,2})); // 3
        System.out.println(singleNumber(new int[]{0,1,0,1,0,1,99})); // 99
        System.out.println(singleNumber(new int[]{-2,-2,1,1,4,1,-2})); // 4
    }
}
