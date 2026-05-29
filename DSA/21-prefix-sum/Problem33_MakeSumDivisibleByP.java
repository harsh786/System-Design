/**
 * Problem 33: Make Sum Divisible by P (LeetCode 1590)
 * 
 * Pattern: Find shortest subarray whose sum mod p == totalSum mod p.
 * Use prefix sum mod + HashMap of last occurrence.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Finding the smallest data segment to remove so remaining
 * data aligns to block boundaries for efficient I/O.
 */
import java.util.*;

public class Problem33_MakeSumDivisibleByP {

    public static int minSubarray(int[] nums, int p) {
        int n = nums.length;
        long total = 0;
        for (int num : nums) total += num;
        int target = (int) (total % p);
        if (target == 0) return 0;

        Map<Integer, Integer> lastIndex = new HashMap<>();
        lastIndex.put(0, -1);
        int minLen = n;
        long prefixMod = 0;
        for (int i = 0; i < n; i++) {
            prefixMod = (prefixMod + nums[i]) % p;
            int need = (int) ((prefixMod - target + p) % p);
            if (lastIndex.containsKey(need))
                minLen = Math.min(minLen, i - lastIndex.get(need));
            lastIndex.put((int) prefixMod, i);
        }
        return minLen == n ? -1 : minLen;
    }

    public static void main(String[] args) {
        assert minSubarray(new int[]{3, 1, 4, 2}, 6) == 1;
        assert minSubarray(new int[]{6, 3, 5, 2}, 9) == 2;
        assert minSubarray(new int[]{1, 2, 3}, 3) == 0;
        assert minSubarray(new int[]{1, 2, 3}, 7) == -1;
        System.out.println("All tests passed!");
    }
}
