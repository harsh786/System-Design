import java.util.*;

public class Problem44_ContainsDuplicateIIIWithTreeSet {
    public static boolean containsNearbyAlmostDuplicate(int[] nums, int indexDiff, int valueDiff) {
        TreeSet<Long> set = new TreeSet<>();
        for (int i = 0; i < nums.length; i++) {
            Long ceil = set.ceiling((long) nums[i] - valueDiff);
            if (ceil != null && ceil <= (long) nums[i] + valueDiff) return true;
            set.add((long) nums[i]);
            if (i >= indexDiff) set.remove((long) nums[i - indexDiff]);
        }
        return false;
    }

    public static void main(String[] args) {
        System.out.println(containsNearbyAlmostDuplicate(new int[]{1,2,3,1}, 3, 0)); // true
        System.out.println(containsNearbyAlmostDuplicate(new int[]{1,5,9,1,5,9}, 2, 3)); // false
    }
}
