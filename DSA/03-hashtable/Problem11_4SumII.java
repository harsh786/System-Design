import java.util.*;

/**
 * Problem 11: 4Sum II
 * Given four arrays A, B, C, D, count tuples (i,j,k,l) where A[i]+B[j]+C[k]+D[l]=0.
 *
 * Approach: Compute all A[i]+B[j] sums in a HashMap, then for each C[k]+D[l],
 * check if -(C[k]+D[l]) exists in the map.
 *
 * Time Complexity: O(n^2)
 * Space Complexity: O(n^2)
 *
 * Production Analogy: Like join optimization in databases - precompute partial joins
 * (hash join) to avoid O(n^4) nested loop scans.
 */
public class Problem11_4SumII {
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
        Problem11_4SumII sol = new Problem11_4SumII();
        System.out.println(sol.fourSumCount(new int[]{1,2}, new int[]{-2,-1}, new int[]{-1,2}, new int[]{0,2})); // 2
        System.out.println(sol.fourSumCount(new int[]{0}, new int[]{0}, new int[]{0}, new int[]{0})); // 1
    }
}
