import java.util.*;

public class Problem33_ContainsDuplicateII {
    public boolean containsNearbyDuplicate(int[] nums, int k) {
        Map<Integer, Integer> map = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            if (map.containsKey(nums[i]) && i - map.get(nums[i]) <= k) return true;
            map.put(nums[i], i);
        }
        return false;
    }

    public static void main(String[] args) {
        Problem33_ContainsDuplicateII sol = new Problem33_ContainsDuplicateII();
        System.out.println(sol.containsNearbyDuplicate(new int[]{1,2,3,1}, 3)); // true
    }
}
