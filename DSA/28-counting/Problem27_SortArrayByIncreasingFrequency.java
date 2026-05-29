/**
 * Problem: Sort Array by Increasing Frequency (LeetCode 1636)
 * Approach: Count frequencies, custom sort
 * Complexity: O(n log n) time, O(n) space
 * Production Analogy: Priority-based reordering in content delivery
 */
import java.util.*;
public class Problem27_SortArrayByIncreasingFrequency {
    public int[] frequencySort(int[] nums) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int n : nums) freq.merge(n, 1, Integer::sum);
        Integer[] boxed = Arrays.stream(nums).boxed().toArray(Integer[]::new);
        Arrays.sort(boxed, (a, b) -> freq.get(a) != freq.get(b) ? freq.get(a) - freq.get(b) : b - a);
        for (int i = 0; i < nums.length; i++) nums[i] = boxed[i];
        return nums;
    }
    public static void main(String[] args) {
        System.out.println(Arrays.toString(new Problem27_SortArrayByIncreasingFrequency()
            .frequencySort(new int[]{1,1,2,2,2,3}))); // [3,1,1,2,2,2]
    }
}
