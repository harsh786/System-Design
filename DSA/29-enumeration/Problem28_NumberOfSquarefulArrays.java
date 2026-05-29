import java.util.*;

public class Problem28_NumberOfSquarefulArrays {
    int count = 0;
    public int numSquarefulPerms(int[] nums) {
        Arrays.sort(nums);
        backtrack(nums, new boolean[nums.length], new ArrayList<>());
        return count;
    }
    private void backtrack(int[] nums, boolean[] used, List<Integer> path) {
        if (path.size() == nums.length) { count++; return; }
        for (int i = 0; i < nums.length; i++) {
            if (used[i]) continue;
            if (i > 0 && nums[i]==nums[i-1] && !used[i-1]) continue;
            if (!path.isEmpty()) { int s = (int)Math.round(Math.sqrt(path.get(path.size()-1)+nums[i])); if (s*s != path.get(path.size()-1)+nums[i]) continue; }
            used[i]=true; path.add(nums[i]); backtrack(nums,used,path); path.remove(path.size()-1); used[i]=false;
        }
    }
    public static void main(String[] args) { System.out.println(new Problem28_NumberOfSquarefulArrays().numSquarefulPerms(new int[]{1,17,8})); }
}
