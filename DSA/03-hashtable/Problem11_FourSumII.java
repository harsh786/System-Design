import java.util.*;

/**
 * Problem 11: 4Sum II
 * Given four arrays, count tuples (i,j,k,l) such that A[i]+B[j]+C[k]+D[l]==0.
 *
 * Approach: Compute all sums of A+B pairs in HashMap. For each C+D pair, check if -(C[k]+D[l]) exists.
 *
 * Time Complexity: O(n^2)
 * Space Complexity: O(n^2)
 *
 * Production Analogy: Multi-dimensional join optimization in databases -
 * pre-computing partial results to avoid full cartesian product scans.
 */
public class Problem11_FourSumII {
    public int fourSumCount(int[] nums1, int[] nums2, int[] nums3, int[] nums4) {
        Map<Integer, Integer> map = new HashMap<>();
        for (int a : nums1)
            for (int b : nums2)
                map.merge(a + b, 1, Integer::sum);
        int count = 0;
        for (int c : nums3)
            for (int d : nums4)
                count += map.getOrDefault(-(c + d), 0);
        return count;
    }

    public static void main(String[] args) {
        Problem11_FourSumII sol = new Problem11_FourSumII();
        System.out.println(sol.fourSumCount(
            new int[]{1,2}, new int[]{-2,-1}, new int[]{-1,2}, new int[]{0,2})); // 2
        System.out.println(sol.fourSumCount(
            new int[]{0}, new int[]{0}, new int[]{0}, new int[]{0})); // 1
    }
}
