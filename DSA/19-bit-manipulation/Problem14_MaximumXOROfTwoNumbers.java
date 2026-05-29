/**
 * Problem 14: Maximum XOR of Two Numbers in an Array
 * 
 * Approach: Build answer bit by bit from MSB. Use HashSet of prefixes to check
 * if candidate (current answer with next bit set) is achievable: if prefix^candidate exists in set.
 * Time: O(32n) = O(n), Space: O(n)
 * 
 * Production Analogy: Finding maximum network path diversity between two nodes.
 */
import java.util.*;

public class Problem14_MaximumXOROfTwoNumbers {
    public static int findMaximumXOR(int[] nums) {
        int max = 0, mask = 0;
        for (int i = 31; i >= 0; i--) {
            mask |= (1 << i);
            Set<Integer> prefixes = new HashSet<>();
            for (int num : nums) prefixes.add(num & mask);
            int candidate = max | (1 << i);
            for (int prefix : prefixes) {
                if (prefixes.contains(prefix ^ candidate)) {
                    max = candidate;
                    break;
                }
            }
        }
        return max;
    }

    public static void main(String[] args) {
        System.out.println(findMaximumXOR(new int[]{3,10,5,25,2,8})); // 28
        System.out.println(findMaximumXOR(new int[]{14,70,53,83,49,91,36,80,92,51,66,70})); // 127
    }
}
