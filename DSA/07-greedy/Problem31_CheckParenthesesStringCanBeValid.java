/**
 * Problem 31: Check if a Parentheses String Can Be Valid (LeetCode 2116)
 *
 * Greedy Choice: Track min/max open parens. Locked chars are fixed; unlocked can be either.
 *
 * Time: O(n), Space: O(1)
 *
 * Production Analogy: Validating configurable bracket expressions where some tokens are flexible.
 */
public class Problem31_CheckParenthesesStringCanBeValid {
    
    public static boolean canBeValid(String s, String locked) {
        if (s.length() % 2 != 0) return false;
        int min = 0, max = 0;
        for (int i = 0; i < s.length(); i++) {
            if (locked.charAt(i) == '0') { min--; max++; }
            else if (s.charAt(i) == '(') { min++; max++; }
            else { min--; max--; }
            if (max < 0) return false;
            min = Math.max(min, 0);
        }
        return min == 0;
    }
    
    public static void main(String[] args) {
        System.out.println(canBeValid("))()))", "010100")); // true
        System.out.println(canBeValid("()()", "0000"));     // true
        System.out.println(canBeValid(")", "0"));           // false
    }
}
