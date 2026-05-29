import java.util.*;

public class Problem48_MaximumNumberOfNonOverlappingSubarrays {
    // LC 1546: Max number of non-overlapping subarrays with sum = target
    public static int maxNonOverlapping(int[] nums, int target) {
        Map<Integer, Integer> prefixMap = new HashMap<>();
        prefixMap.put(0, -1);
        int sum = 0, count = 0, lastEnd = -1;
        for (int i = 0; i < nums.length; i++) {
            sum += nums[i];
            if (prefixMap.containsKey(sum - target)) {
                int start = prefixMap.get(sum - target) + 1;
                if (start >= lastEnd) {
                    count++;
                    lastEnd = i + 1;
                }
            }
            prefixMap.put(sum, i);
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(maxNonOverlapping(new int[]{1,1,1,1,1}, 2)); // 2
        System.out.println(maxNonOverlapping(new int[]{-1,3,5,1,4,2,-9}, 6)); // 2
    }
}
