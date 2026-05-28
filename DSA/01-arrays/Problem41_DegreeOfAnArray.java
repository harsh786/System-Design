import java.util.*;

/**
 * Problem 41: Degree of an Array
 * Find shortest subarray with same degree as the array.
 * Degree = max frequency of any element.
 * 
 * Production Analogy: Like finding the minimum time window containing all occurrences
 * of the most frequent event type in a log stream.
 * 
 * O(n) time, O(n) space - track first/last occurrence and count per element
 */
public class Problem41_DegreeOfAnArray {

    public static int findShortestSubArray(int[] nums) {
        Map<Integer, Integer> count = new HashMap<>(), first = new HashMap<>();
        int degree = 0, minLen = 0;
        for (int i = 0; i < nums.length; i++) {
            first.putIfAbsent(nums[i], i);
            count.merge(nums[i], 1, Integer::sum);
            int c = count.get(nums[i]);
            if (c > degree) { degree = c; minLen = i - first.get(nums[i]) + 1; }
            else if (c == degree) minLen = Math.min(minLen, i - first.get(nums[i]) + 1);
        }
        return minLen;
    }

    public static void main(String[] args) {
        System.out.println(findShortestSubArray(new int[]{1,2,2,3,1}));   // 2
        System.out.println(findShortestSubArray(new int[]{1,2,2,3,1,4,2})); // 6
    }
}
