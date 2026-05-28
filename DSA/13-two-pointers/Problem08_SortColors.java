/**
 * Problem 8: Sort Colors (Dutch National Flag)
 * 
 * Sort array with values 0, 1, 2 in-place in one pass.
 * 
 * Approach: Three pointers - low (0s boundary), mid (current), high (2s boundary).
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like triaging support tickets into P0/P1/P2 queues
 * in a single pass through an incident stream.
 */
public class Problem08_SortColors {
    public static void sortColors(int[] nums) {
        int low = 0, mid = 0, high = nums.length - 1;
        while (mid <= high) {
            if (nums[mid] == 0) {
                swap(nums, low++, mid++);
            } else if (nums[mid] == 1) {
                mid++;
            } else {
                swap(nums, mid, high--);
            }
        }
    }

    private static void swap(int[] nums, int i, int j) {
        int tmp = nums[i]; nums[i] = nums[j]; nums[j] = tmp;
    }

    public static void main(String[] args) {
        int[] a = {2,0,2,1,1,0};
        sortColors(a);
        System.out.println(java.util.Arrays.toString(a)); // [0,0,1,1,2,2]

        int[] b = {2,0,1};
        sortColors(b);
        System.out.println(java.util.Arrays.toString(b)); // [0,1,2]
    }
}
