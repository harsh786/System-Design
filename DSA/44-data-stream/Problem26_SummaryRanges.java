import java.util.*;

public class Problem26_SummaryRanges {
    // 228. Summary Ranges (stream variant).
    
    public List<String> summaryRanges(int[] nums) {
        List<String> res = new ArrayList<>();
        int i = 0;
        while (i < nums.length) {
            int start = nums[i];
            while (i + 1 < nums.length && nums[i+1] == nums[i] + 1) i++;
            if (nums[i] == start) res.add(String.valueOf(start));
            else res.add(start + "->" + nums[i]);
            i++;
        }
        return res;
    }
    
    public static void main(String[] args) {
        Problem26_SummaryRanges sol = new Problem26_SummaryRanges();
        System.out.println(sol.summaryRanges(new int[]{0,1,2,4,5,7})); // [0->2, 4->5, 7]
    }
}
