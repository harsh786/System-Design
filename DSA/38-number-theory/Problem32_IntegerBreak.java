package numbertheory;

/**
 * Problem 32: Integer Break (LeetCode 343)
 * 
 * Approach: Math insight: split into 3s as much as possible (except leave 4 as 2*2).
 * 
 * Time Complexity: O(n/3) or O(1) with formula
 * Space Complexity: O(1)
 */
public class Problem32_IntegerBreak {
    
    public int integerBreak(int n) {
        if (n == 2) return 1;
        if (n == 3) return 2;
        int product = 1;
        while (n > 4) { product *= 3; n -= 3; }
        return product * n;
    }
    
    public static void main(String[] args) {
        Problem32_IntegerBreak sol = new Problem32_IntegerBreak();
        System.out.println(sol.integerBreak(10)); // 36
        System.out.println(sol.integerBreak(8));  // 18
    }
}
