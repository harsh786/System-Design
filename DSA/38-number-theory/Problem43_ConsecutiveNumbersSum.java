package numbertheory;

/**
 * Problem 43: Consecutive Numbers Sum (LeetCode 829)
 * 
 * Approach: n = k*x + k*(k-1)/2 for k consecutive numbers starting at x.
 * So n - k*(k-1)/2 must be positive and divisible by k.
 * 
 * Time Complexity: O(sqrt(n))
 * Space Complexity: O(1)
 */
public class Problem43_ConsecutiveNumbersSum {
    
    public int consecutiveNumbersSum(int n) {
        int count = 0;
        for (int k = 1; k * (k - 1) / 2 < n; k++) {
            if ((n - k * (k - 1) / 2) % k == 0) count++;
        }
        return count;
    }
    
    public static void main(String[] args) {
        Problem43_ConsecutiveNumbersSum sol = new Problem43_ConsecutiveNumbersSum();
        System.out.println(sol.consecutiveNumbersSum(15)); // 4
        System.out.println(sol.consecutiveNumbersSum(9));  // 3
    }
}
