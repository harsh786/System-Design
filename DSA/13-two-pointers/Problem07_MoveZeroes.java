/**
 * Problem 7: Move Zeroes
 * 
 * Move all zeroes to end while maintaining relative order of non-zero elements.
 * 
 * Approach: Slow pointer for next non-zero position, fast scans all elements.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like compacting a memory allocator - moving live objects
 * to the front and freeing trailing space.
 */
public class Problem07_MoveZeroes {
    public static void moveZeroes(int[] nums) {
        int slow = 0;
        for (int fast = 0; fast < nums.length; fast++) {
            if (nums[fast] != 0) {
                int tmp = nums[slow];
                nums[slow] = nums[fast];
                nums[fast] = tmp;
                slow++;
            }
        }
    }

    public static void main(String[] args) {
        int[] a = {0,1,0,3,12};
        moveZeroes(a);
        System.out.println(java.util.Arrays.toString(a)); // [1,3,12,0,0]

        int[] b = {0};
        moveZeroes(b);
        System.out.println(java.util.Arrays.toString(b)); // [0]

        int[] c = {1,2,3};
        moveZeroes(c);
        System.out.println(java.util.Arrays.toString(c)); // [1,2,3]
    }
}
