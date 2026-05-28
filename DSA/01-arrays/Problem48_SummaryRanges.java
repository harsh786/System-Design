import java.util.*;

/**
 * Problem 48: Summary Ranges
 * Return smallest sorted list of ranges covering all numbers in the array.
 * 
 * Production Analogy: Like compressing IP ranges in a firewall rule -
 * consecutive IPs become a single CIDR-like range.
 * 
 * O(n) time, O(1) space (excluding output)
 */
public class Problem48_SummaryRanges {

    public static List<String> summaryRanges(int[] nums) {
        List<String> result = new ArrayList<>();
        for (int i = 0; i < nums.length; i++) {
            int start = nums[i];
            while (i + 1 < nums.length && nums[i+1] == nums[i] + 1) i++;
            if (start == nums[i]) result.add(String.valueOf(start));
            else result.add(start + "->" + nums[i]);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(summaryRanges(new int[]{0,1,2,4,5,7}));  // [0->2, 4->5, 7]
        System.out.println(summaryRanges(new int[]{0,2,3,4,6,8,9}));// [0, 2->4, 6, 8->9]
        System.out.println(summaryRanges(new int[]{}));               // []
    }
}
