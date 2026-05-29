/**
 * Problem: Find the Most Competitive Subsequence (LC 1673)
 * Monotonic stack (related to monotonic queue) - maintain smallest possible sequence.
 * Time: O(n) | Space: O(n)
 * Production Analogy: Selecting top-k candidates maintaining relative order.
 */
import java.util.*;

public class Problem16_MostCompetitiveSubsequence {
    public static int[] mostCompetitive(int[] nums, int k) {
        int n = nums.length;
        Deque<Integer> stack = new ArrayDeque<>();
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && stack.peekLast() > nums[i] && stack.size() + (n - i) > k) stack.pollLast();
            if (stack.size() < k) stack.offerLast(nums[i]);
        }
        int[] result = new int[k];
        for (int i = 0; i < k; i++) result[i] = stack.pollFirst();
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(mostCompetitive(new int[]{3,5,2,6}, 2))); // [2,6]
        System.out.println(Arrays.toString(mostCompetitive(new int[]{2,4,3,3,5,4,9,6}, 4))); // [2,3,3,4]
    }
}
