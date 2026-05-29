import java.util.*;

public class Problem08_Permutations {
    public static List<List<Integer>> permute(int[] nums) {
        List<List<Integer>> res = new ArrayList<>();
        backtrack(res, new ArrayList<>(), nums, new boolean[nums.length]);
        return res;
    }
    static void backtrack(List<List<Integer>> res, List<Integer> cur, int[] nums, boolean[] used) {
        if (cur.size() == nums.length) { res.add(new ArrayList<>(cur)); return; }
        for (int i = 0; i < nums.length; i++) {
            if (used[i]) continue;
            used[i] = true; cur.add(nums[i]);
            backtrack(res, cur, nums, used);
            cur.remove(cur.size() - 1); used[i] = false;
        }
    }
    public static void main(String[] args) {
        System.out.println(permute(new int[]{1, 2, 3}));
    }
}
