import java.util.*;

public class Problem02_SubsetsII {
    public List<List<Integer>> subsetsWithDup(int[] nums) {
        Arrays.sort(nums);
        Set<List<Integer>> set = new HashSet<>();
        int n = nums.length;
        for (int mask = 0; mask < (1 << n); mask++) {
            List<Integer> subset = new ArrayList<>();
            for (int i = 0; i < n; i++) if ((mask & (1 << i)) != 0) subset.add(nums[i]);
            set.add(subset);
        }
        return new ArrayList<>(set);
    }

    public static void main(String[] args) {
        System.out.println(new Problem02_SubsetsII().subsetsWithDup(new int[]{1,2,2}));
    }
}
