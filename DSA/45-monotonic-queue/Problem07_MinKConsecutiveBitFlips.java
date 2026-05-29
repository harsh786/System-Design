/**
 * Problem: Minimum Number of K Consecutive Bit Flips (LC 995)
 * Greedy + sliding window tracking flip count using deque.
 * Time: O(n) | Space: O(n)
 * Production Analogy: Minimum corrections needed in a data stream with fixed correction span.
 */
import java.util.*;

public class Problem07_MinKConsecutiveBitFlips {
    public static int minKBitFlips(int[] nums, int k) {
        int n = nums.length, flips = 0, flipCount = 0;
        Deque<Integer> deque = new ArrayDeque<>();
        for (int i = 0; i < n; i++) {
            if (!deque.isEmpty() && deque.peekFirst() <= i - k) { deque.pollFirst(); flipCount--; }
            if ((nums[i] + flipCount) % 2 == 0) {
                if (i + k > n) return -1;
                deque.offerLast(i); flipCount++; flips++;
            }
        }
        return flips;
    }

    public static void main(String[] args) {
        System.out.println(minKBitFlips(new int[]{0,1,0}, 1)); // 2
        System.out.println(minKBitFlips(new int[]{1,1,0}, 2)); // -1
        System.out.println(minKBitFlips(new int[]{0,0,0,1,0,1,1,0}, 3)); // 3
    }
}
