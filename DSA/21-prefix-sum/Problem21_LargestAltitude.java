/**
 * Problem 21: Find the Highest Altitude (LeetCode 1732)
 * 
 * Pattern: Running prefix sum, track max
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Tracking peak memory usage given delta changes per operation.
 */
public class Problem21_LargestAltitude {

    public static int largestAltitude(int[] gain) {
        int max = 0, curr = 0;
        for (int g : gain) {
            curr += g;
            max = Math.max(max, curr);
        }
        return max;
    }

    public static void main(String[] args) {
        assert largestAltitude(new int[]{-5, 1, 5, 0, -7}) == 1;
        assert largestAltitude(new int[]{-4, -3, -2, -1, 4, 3, 2}) == 0;
        System.out.println("All tests passed!");
    }
}
