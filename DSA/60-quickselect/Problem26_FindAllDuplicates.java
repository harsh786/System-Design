import java.util.*;

public class Problem26_FindAllDuplicates {
    public List<Integer> findDuplicates(int[] nums) {
        List<Integer> res = new ArrayList<>();
        for (int i = 0; i < nums.length; i++) {
            int idx = Math.abs(nums[i]) - 1;
            if (nums[idx] < 0) res.add(idx + 1);
            else nums[idx] = -nums[idx];
        }
        return res;
    }

    public static void main(String[] args) {
        Problem26_FindAllDuplicates sol = new Problem26_FindAllDuplicates();
        System.out.println(sol.findDuplicates(new int[]{4,3,2,7,8,2,3,1}));
    }
}
