import java.util.*;

public class Problem15_SummaryRanges {
    // LC 228: Return shortest sorted list of ranges covering all numbers
    public static List<String> summaryRanges(int[] nums) {
        List<String> res = new ArrayList<>();
        int i = 0;
        while (i < nums.length) {
            int start = nums[i];
            while (i + 1 < nums.length && nums[i + 1] == nums[i] + 1) i++;
            if (nums[i] == start) res.add(String.valueOf(start));
            else res.add(start + "->" + nums[i]);
            i++;
        }
        return res;
    }

    public static void main(String[] args) {
        System.out.println(summaryRanges(new int[]{0,1,2,4,5,7})); // [0->2, 4->5, 7]
    }
}
