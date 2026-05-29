import java.util.*;

public class Problem02_SubsetsII {
    public List<List<Integer>> subsetsWithDup(int[] nums) {
        List<List<Integer>> result = new ArrayList<>();
        Arrays.sort(nums);
        backtrack(result, new ArrayList<>(), nums, 0);
        return result;
    }

    private void backtrack(List<List<Integer>> result, List<Integer> temp, int[] nums, int start) {
        result.add(new ArrayList<>(temp));
        for (int i = start; i < nums.length; i++) {
            if (i > start && nums[i] == nums[i-1]) continue;
            temp.add(nums[i]); backtrack(result, temp, nums, i+1); temp.remove(temp.size()-1);
        }
    }

    public static void main(String[] args) { System.out.println(new Problem02_SubsetsII().subsetsWithDup(new int[]{1,2,2})); }
}
