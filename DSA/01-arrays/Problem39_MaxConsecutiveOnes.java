/**
 * Problem 39: Max Consecutive Ones
 * Find maximum number of consecutive 1's in a binary array.
 * 
 * Production Analogy: Like measuring longest uptime streak from a health check log.
 * 
 * O(n) time, O(1) space
 */
public class Problem39_MaxConsecutiveOnes {

    public static int findMaxConsecutiveOnes(int[] nums) {
        int max = 0, count = 0;
        for (int n : nums) {
            if (n == 1) max = Math.max(max, ++count);
            else count = 0;
        }
        return max;
    }

    public static void main(String[] args) {
        System.out.println(findMaxConsecutiveOnes(new int[]{1,1,0,1,1,1})); // 3
        System.out.println(findMaxConsecutiveOnes(new int[]{1,0,1,1,0,1})); // 2
        System.out.println(findMaxConsecutiveOnes(new int[]{0}));             // 0
    }
}
