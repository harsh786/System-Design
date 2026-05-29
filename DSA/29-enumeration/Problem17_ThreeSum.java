import java.util.*;

public class Problem17_ThreeSum {
    public List<List<Integer>> threeSum(int[] nums) {
        List<List<Integer>> result = new ArrayList<>();
        Arrays.sort(nums);
        for (int i = 0; i < nums.length-2; i++) {
            if (i > 0 && nums[i]==nums[i-1]) continue;
            int lo = i+1, hi = nums.length-1;
            while (lo < hi) {
                int sum = nums[i]+nums[lo]+nums[hi];
                if (sum == 0) { result.add(Arrays.asList(nums[i],nums[lo],nums[hi])); while(lo<hi&&nums[lo]==nums[lo+1])lo++; while(lo<hi&&nums[hi]==nums[hi-1])hi--; lo++;hi--; }
                else if (sum < 0) lo++; else hi--;
            }
        }
        return result;
    }

    public static void main(String[] args) { System.out.println(new Problem17_ThreeSum().threeSum(new int[]{-1,0,1,2,-1,-4})); }
}
