/**
 * Problem: 4Sum II (LeetCode 454)
 * Approach: Split into two pairs, count complement sums
 * Complexity: O(n^2) time, O(n^2) space
 * Production Analogy: Meet-in-the-middle search optimization in cryptanalysis
 */
import java.util.*;
public class Problem41_FourSumII {
    public int fourSumCount(int[] nums1, int[] nums2, int[] nums3, int[] nums4) {
        Map<Integer, Integer> map = new HashMap<>();
        for (int a : nums1) for (int b : nums2) map.merge(a+b, 1, Integer::sum);
        int count = 0;
        for (int c : nums3) for (int d : nums4) count += map.getOrDefault(-(c+d), 0);
        return count;
    }
    public static void main(String[] args) {
        System.out.println(new Problem41_FourSumII().fourSumCount(
            new int[]{1,2}, new int[]{-2,-1}, new int[]{-1,2}, new int[]{0,2})); // 2
    }
}
