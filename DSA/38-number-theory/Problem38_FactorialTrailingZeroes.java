package numbertheory;

/**
 * Problem 38: Factorial Trailing Zeroes (LeetCode 172)
 * 
 * Approach: Count factors of 5 in n! = n/5 + n/25 + n/125 + ...
 * 
 * Time Complexity: O(log n)
 * Space Complexity: O(1)
 */
public class Problem38_FactorialTrailingZeroes {
    
    public int trailingZeroes(int n) {
        int count = 0;
        while (n >= 5) { n /= 5; count += n; }
        return count;
    }
    
    public static void main(String[] args) {
        Problem38_FactorialTrailingZeroes sol = new Problem38_FactorialTrailingZeroes();
        System.out.println(sol.trailingZeroes(25));  // 6
        System.out.println(sol.trailingZeroes(100)); // 24
    }
}
