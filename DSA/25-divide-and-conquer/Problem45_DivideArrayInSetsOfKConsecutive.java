import java.util.*;

/**
 * Problem 45: Divide Array in Sets of K Consecutive Numbers (LeetCode 1296)
 * 
 * Greedy + D&C Mindset:
 * - Sort array, then greedily form groups starting from smallest available
 * - DIVIDE: Separate into groups of k consecutive numbers
 * - CONQUER: After removing a valid group, recurse on remaining
 * - COMBINE: All groups valid => true
 * 
 * Time: O(n log n) for sorting + O(n) for greedy
 * Space: O(n) for TreeMap
 * 
 * Production Analogy:
 * - Batch processing: dividing work items into sequential batches
 * - Card game hand evaluation (forming sequences/runs)
 * - Resource allocation in consecutive time slots
 */
public class Problem45_DivideArrayInSetsOfKConsecutive {

    public static boolean isPossibleDivide(int[] nums, int k) {
        if (nums.length % k != 0) return false;
        
        TreeMap<Integer, Integer> count = new TreeMap<>();
        for (int n : nums) count.merge(n, 1, Integer::sum);
        
        while (!count.isEmpty()) {
            int first = count.firstKey();
            for (int i = first; i < first + k; i++) {
                Integer freq = count.get(i);
                if (freq == null) return false;
                if (freq == 1) count.remove(i);
                else count.put(i, freq - 1);
            }
        }
        return true;
    }

    public static void main(String[] args) {
        System.out.println(isPossibleDivide(new int[]{1,2,3,3,4,4,5,6}, 4));     // true
        System.out.println(isPossibleDivide(new int[]{3,2,1,2,3,4,3,4,5,9,10,11}, 3)); // true
        System.out.println(isPossibleDivide(new int[]{3,3,2,2,1,1}, 3));          // true
        System.out.println(isPossibleDivide(new int[]{1,2,3,4}, 3));              // false
        System.out.println(isPossibleDivide(new int[]{1}, 1));                    // true
    }
}
