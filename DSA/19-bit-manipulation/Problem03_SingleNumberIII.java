/**
 * Problem 3: Single Number III
 * Two elements appear once, rest appear twice. Find both.
 * 
 * Approach: XOR all to get xor of two unique nums. Use lowest set bit to partition.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Identifying two anomalous microservices among paired replicas.
 */
public class Problem03_SingleNumberIII {
    public static int[] singleNumber(int[] nums) {
        int xor = 0;
        for (int n : nums) xor ^= n;
        // Get rightmost set bit (differs between the two numbers)
        int diff = xor & (-xor);
        int a = 0;
        for (int n : nums) {
            if ((n & diff) != 0) a ^= n;
        }
        return new int[]{a, xor ^ a};
    }

    public static void main(String[] args) {
        int[] r = singleNumber(new int[]{1,2,1,3,2,5});
        System.out.println(r[0] + " " + r[1]); // 3 5 (or 5 3)
        r = singleNumber(new int[]{-1,0});
        System.out.println(r[0] + " " + r[1]); // -1 0
    }
}
