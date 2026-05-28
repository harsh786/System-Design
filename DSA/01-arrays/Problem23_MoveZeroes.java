import java.util.*;

/**
 * Problem 23: Move Zeroes
 * Move all 0's to end maintaining relative order of non-zero elements.
 * 
 * Production Analogy: Like compacting a log-structured storage - move live data
 * forward, leave free space at the end (LSM compaction).
 * 
 * O(n) time, O(1) space - two pointer (write pointer for non-zeros)
 */
public class Problem23_MoveZeroes {

    public static void moveZeroes(int[] nums) {
        int write = 0;
        for (int i = 0; i < nums.length; i++)
            if (nums[i] != 0) nums[write++] = nums[i];
        while (write < nums.length) nums[write++] = 0;
    }

    public static void main(String[] args) {
        int[] a = {0,1,0,3,12}; moveZeroes(a); System.out.println(Arrays.toString(a)); // [1,3,12,0,0]
        int[] b = {0}; moveZeroes(b); System.out.println(Arrays.toString(b)); // [0]
        int[] c = {1}; moveZeroes(c); System.out.println(Arrays.toString(c)); // [1]
    }
}
