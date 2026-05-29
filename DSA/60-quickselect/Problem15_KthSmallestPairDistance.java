import java.util.*;

public class Problem15_KthSmallestPairDistance {
    /*
     * Kth Smallest Pair Distance - Binary search + counting
     * Time: O(n log n + n log W) where W is max distance
     */
    public int smallestDistancePair(int[] nums, int k) {
        Arrays.sort(nums);
        int lo = 0, hi = nums[nums.length - 1] - nums[0];
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (countPairs(nums, mid) >= k) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }

    private int countPairs(int[] nums, int maxDist) {
        int count = 0, left = 0;
        for (int right = 0; right < nums.length; right++) {
            while (nums[right] - nums[left] > maxDist) left++;
            count += right - left;
        }
        return count;
    }

    public static void main(String[] args) {
        Problem15_KthSmallestPairDistance sol = new Problem15_KthSmallestPairDistance();
        System.out.println(sol.smallestDistancePair(new int[]{1, 3, 1}, 1)); // 0
        System.out.println(sol.smallestDistancePair(new int[]{1, 6, 1}, 3)); // 5
    }
}
