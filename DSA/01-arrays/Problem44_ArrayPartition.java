import java.util.*;

/**
 * Problem 44: Array Partition
 * Pair up 2n integers, maximize sum of min(ai, bi) for all pairs.
 * 
 * Production Analogy: Like pairing servers for failover - sort by capacity and pair
 * adjacent ones to maximize the minimum guaranteed capacity.
 * 
 * O(n log n) time, O(1) space - sort and sum every other element
 */
public class Problem44_ArrayPartition {

    public static int arrayPairSum(int[] nums) {
        Arrays.sort(nums);
        int sum = 0;
        for (int i = 0; i < nums.length; i += 2) sum += nums[i];
        return sum;
    }

    public static void main(String[] args) {
        System.out.println(arrayPairSum(new int[]{1,4,3,2}));     // 4
        System.out.println(arrayPairSum(new int[]{6,2,6,5,1,2})); // 9
    }
}
