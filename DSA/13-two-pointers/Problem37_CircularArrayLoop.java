/**
 * Problem 37: Circular Array Loop
 * 
 * Determine if there's a cycle of length > 1 in a circular array where
 * nums[i] indicates steps to move. All elements in cycle must have same sign.
 * 
 * Approach: For each index, slow/fast pointer. Validate same direction and length > 1.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like detecting circular dependencies in a build system
 * where dependencies are directional (forward/backward).
 */
public class Problem37_CircularArrayLoop {
    public static boolean circularArrayLoop(int[] nums) {
        int n = nums.length;
        for (int i = 0; i < n; i++) {
            if (nums[i] == 0) continue;
            int slow = i, fast = i;
            while (nums[advance(slow, nums)] * nums[i] > 0 &&
                   nums[advance(fast, nums)] * nums[i] > 0 &&
                   nums[advance(advance(fast, nums), nums)] * nums[i] > 0) {
                slow = advance(slow, nums);
                fast = advance(advance(fast, nums), nums);
                if (slow == fast) {
                    if (slow == advance(slow, nums)) break; // length 1
                    return true;
                }
            }
            // Mark visited nodes as 0
            int j = i;
            while (nums[j] * nums[i] > 0) {
                int next = advance(j, nums);
                nums[j] = 0;
                j = next;
            }
        }
        return false;
    }

    private static int advance(int idx, int[] nums) {
        int n = nums.length;
        return ((idx + nums[idx]) % n + n) % n;
    }

    public static void main(String[] args) {
        System.out.println(circularArrayLoop(new int[]{2,-1,1,2,2})); // true
        System.out.println(circularArrayLoop(new int[]{-1,2})); // false
        System.out.println(circularArrayLoop(new int[]{-2,1,-1,-2,-2})); // false
    }
}
