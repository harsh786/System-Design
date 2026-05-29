package numbertheory;

/**
 * Problem 6: Power of Two (LeetCode 231)
 * 
 * Approach: n > 0 && (n & (n-1)) == 0
 * 
 * Time Complexity: O(1)
 * Space Complexity: O(1)
 */
public class Problem06_PowerOfTwo {
    
    public boolean isPowerOfTwo(int n) { return n > 0 && (n & (n - 1)) == 0; }
    
    public static void main(String[] args) {
        Problem06_PowerOfTwo sol = new Problem06_PowerOfTwo();
        System.out.println(sol.isPowerOfTwo(16)); // true
        System.out.println(sol.isPowerOfTwo(18)); // false
    }
}
