import java.util.*;

public class Problem06_Permutations {
    public List<List<Integer>> permute(int[] nums) {
        List<List<Integer>> result = new ArrayList<>();
        backtrack(result, new ArrayList<>(), nums, new boolean[nums.length]);
        return result;
    }

    private void backtrack(List<List<Integer>> result, List<Integer> temp, int[] nums, boolean[] used) {
        if (temp.size() == nums.length) { result.add(new ArrayList<>(temp)); return; }
        for (int i = 0; i < nums.length; i++) {
            if (used[i]) continue;
            used[i] = true; temp.add(nums[i]);
            backtrack(result, temp, nums, used);
            used[i] = false; temp.remove(temp.size() - 1);
        }
    }

    public static void main(String[] args) {
        System.out.println(new Problem06_Permutations().permute(new int[]{1,2,3}));
    }
}
