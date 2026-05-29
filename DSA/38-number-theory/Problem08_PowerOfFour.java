package numbertheory;

/**
 * Problem 8: Power of Four (LeetCode 342)
 * 
 * Approach: Power of 2 AND bits at even positions: (n & 0xAAAAAAAA) == 0
 * 
 * Time Complexity: O(1)
 * Space Complexity: O(1)
 */
public class Problem08_PowerOfFour {
    
    public boolean isPowerOfFour(int n) {
        return n > 0 && (n & (n - 1)) == 0 && (n & 0xAAAAAAAA) == 0;
    }
    
    public static void main(String[] args) {
        Problem08_PowerOfFour sol = new Problem08_PowerOfFour();
        System.out.println(sol.isPowerOfFour(16)); // true
        System.out.println(sol.isPowerOfFour(8));  // false
    }
}
