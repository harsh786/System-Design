package numbertheory;

/**
 * Problem 7: Power of Three (LeetCode 326)
 * 
 * Approach: 3^19 = 1162261467 is largest power of 3 fitting int. Check divisibility.
 * 
 * Time Complexity: O(1)
 * Space Complexity: O(1)
 */
public class Problem07_PowerOfThree {
    
    public boolean isPowerOfThree(int n) { return n > 0 && 1162261467 % n == 0; }
    
    public static void main(String[] args) {
        Problem07_PowerOfThree sol = new Problem07_PowerOfThree();
        System.out.println(sol.isPowerOfThree(27)); // true
        System.out.println(sol.isPowerOfThree(45)); // false
    }
}
