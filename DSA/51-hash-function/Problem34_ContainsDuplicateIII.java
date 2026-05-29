import java.util.*;

public class Problem34_ContainsDuplicateIII {
    public boolean containsNearbyAlmostDuplicate(int[] nums, int indexDiff, int valueDiff) {
        if (valueDiff < 0) return false;
        Map<Long, Long> buckets = new HashMap<>();
        long w = (long) valueDiff + 1;
        for (int i = 0; i < nums.length; i++) {
            long id = getBucket(nums[i], w);
            if (buckets.containsKey(id)) return true;
            if (buckets.containsKey(id - 1) && Math.abs(nums[i] - buckets.get(id - 1)) < w) return true;
            if (buckets.containsKey(id + 1) && Math.abs(nums[i] - buckets.get(id + 1)) < w) return true;
            buckets.put(id, (long) nums[i]);
            if (i >= indexDiff) buckets.remove(getBucket(nums[i - indexDiff], w));
        }
        return false;
    }

    private long getBucket(long num, long w) { return num < 0 ? (num + 1) / w - 1 : num / w; }

    public static void main(String[] args) {
        Problem34_ContainsDuplicateIII sol = new Problem34_ContainsDuplicateIII();
        System.out.println(sol.containsNearbyAlmostDuplicate(new int[]{1,2,3,1}, 3, 0)); // true
    }
}
