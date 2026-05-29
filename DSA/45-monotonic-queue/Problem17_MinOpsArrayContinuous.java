/**
 * Problem: Minimum Operations to Make Array Continuous (LC 2009)
 * Sort + sliding window to find max elements fitting in range of size n.
 * Time: O(n) | Space: O(n)
 * Production Analogy: Minimum patches to make version numbers consecutive.
 */
import java.util.*;

public class Problem17_MinOpsArrayContinuous {
    public static int minOperations(int[] nums) {
        int n = nums.length;
        TreeSet<Integer> set = new TreeSet<>();
        for (int x : nums) set.add(x);
        int[] sorted = new int[set.size()];
        int idx = 0;
        for (int x : set) sorted[idx++] = x;
        int ans = n;
        int right = 0;
        for (int left = 0; left < sorted.length; left++) {
            while (right < sorted.length && sorted[right] <= sorted[left] + n - 1) right++;
            ans = Math.min(ans, n - (right - left));
        }
        return ans;
    }

    public static void main(String[] args) {
        System.out.println(minOperations(new int[]{4,2,5,3})); // 0
        System.out.println(minOperations(new int[]{1,2,3,5,6})); // 1
    }
}
