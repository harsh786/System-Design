import java.util.*;

/**
 * Problem 47: Find All Numbers Disappeared in an Array
 * Array of [1,n], find all numbers in [1,n] not present.
 * 
 * Production Analogy: Like finding missing sequence numbers in a message queue -
 * use index marking to detect gaps without extra space.
 * 
 * O(n) time, O(1) space - negate at index to mark presence
 */
public class Problem47_FindAllNumbersDisappearedInAnArray {

    public static List<Integer> findDisappearedNumbers(int[] nums) {
        for (int n : nums) {
            int idx = Math.abs(n) - 1;
            if (nums[idx] > 0) nums[idx] = -nums[idx];
        }
        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < nums.length; i++)
            if (nums[i] > 0) result.add(i + 1);
        return result;
    }

    public static void main(String[] args) {
        System.out.println(findDisappearedNumbers(new int[]{4,3,2,7,8,2,3,1})); // [5,6]
        System.out.println(findDisappearedNumbers(new int[]{1,1}));               // [2]
    }
}
