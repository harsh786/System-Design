import java.util.*;

public class Problem01_ContainsDuplicateIII {
    // LC 220: Given array, find if there are two distinct indices i,j such that
    // abs(nums[i]-nums[j]) <= valueDiff and abs(i-j) <= indexDiff
    // Approach: Use TreeSet as sliding window of size indexDiff
    // Time: O(n log k) where k = indexDiff
    public static boolean containsNearbyAlmostDuplicate(int[] nums, int indexDiff, int valueDiff) {
        TreeSet<Long> set = new TreeSet<>();
        for (int i = 0; i < nums.length; i++) {
            long val = (long) nums[i];
            Long floor = set.floor(val + valueDiff);
            if (floor != null && floor >= val - valueDiff) return true;
            set.add(val);
            if (i >= indexDiff) set.remove((long) nums[i - indexDiff]);
        }
        return false;
    }

    public static void main(String[] args) {
        System.out.println(containsNearbyAlmostDuplicate(new int[]{1,2,3,1}, 3, 0)); // true
        System.out.println(containsNearbyAlmostDuplicate(new int[]{1,5,9,1,5,9}, 2, 3)); // false
    }
}
