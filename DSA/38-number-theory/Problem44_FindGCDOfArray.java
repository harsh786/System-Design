package numbertheory;

/**
 * Problem 44: Find Greatest Common Divisor of Array (LeetCode 1979)
 * 
 * Approach: GCD of min and max element.
 * 
 * Time Complexity: O(n + log(max))
 * Space Complexity: O(1)
 */
public class Problem44_FindGCDOfArray {
    
    public int findGCD(int[] nums) {
        int min = Integer.MAX_VALUE, max = Integer.MIN_VALUE;
        for (int n : nums) { min = Math.min(min, n); max = Math.max(max, n); }
        return gcd(min, max);
    }
    
    private int gcd(int a, int b) { return b == 0 ? a : gcd(b, a % b); }
    
    public static void main(String[] args) {
        Problem44_FindGCDOfArray sol = new Problem44_FindGCDOfArray();
        System.out.println(sol.findGCD(new int[]{2, 5, 6, 9, 10})); // 2
    }
}
