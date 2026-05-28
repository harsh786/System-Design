import java.util.*;

/**
 * Problem 28: Find All Duplicates in an Array
 * Elements in [1,n], some appear twice. Find all duplicates in O(n) time, O(1) space.
 * 
 * Production Analogy: Like marking visited nodes in a graph traversal using
 * the data structure itself (sign-flipping as visited marker).
 * 
 * O(n) time, O(1) space - negate value at index to mark as seen
 */
public class Problem28_FindAllDuplicatesInAnArray {

    public static List<Integer> findDuplicates(int[] nums) {
        List<Integer> result = new ArrayList<>();
        for (int n : nums) {
            int idx = Math.abs(n) - 1;
            if (nums[idx] < 0) result.add(idx + 1);
            else nums[idx] = -nums[idx];
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(findDuplicates(new int[]{4,3,2,7,8,2,3,1})); // [2,3]
        System.out.println(findDuplicates(new int[]{1,1,2}));             // [1]
        System.out.println(findDuplicates(new int[]{1}));                  // []
    }
}
