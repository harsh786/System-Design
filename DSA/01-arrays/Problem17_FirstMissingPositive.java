/**
 * Problem 17: First Missing Positive
 * Find the smallest missing positive integer in O(n) time, O(1) space.
 * 
 * Production Analogy: Like finding the first available slot in a pre-allocated 
 * connection pool - use the array itself as a hash table (index = value mapping).
 * 
 * O(n) time, O(1) space - cyclic sort / index-as-hash technique
 */
public class Problem17_FirstMissingPositive {

    public static int firstMissingPositive(int[] nums) {
        int n = nums.length;
        // Place each number in its correct index: nums[i] should be i+1
        for (int i = 0; i < n; i++) {
            while (nums[i] > 0 && nums[i] <= n && nums[nums[i]-1] != nums[i]) {
                int tmp = nums[nums[i]-1]; nums[nums[i]-1] = nums[i]; nums[i] = tmp;
            }
        }
        for (int i = 0; i < n; i++)
            if (nums[i] != i + 1) return i + 1;
        return n + 1;
    }

    public static void main(String[] args) {
        System.out.println(firstMissingPositive(new int[]{1,2,0}));      // 3
        System.out.println(firstMissingPositive(new int[]{3,4,-1,1}));   // 2
        System.out.println(firstMissingPositive(new int[]{7,8,9,11,12}));// 1
        System.out.println(firstMissingPositive(new int[]{1}));           // 2
    }
}
