package numbertheory;

import java.util.Arrays;

/**
 * Problem 28: Plus One (LeetCode 66)
 * 
 * Approach: Add 1 from last digit, propagate carry.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n) worst case (all 9s)
 */
public class Problem28_PlusOne {
    
    public int[] plusOne(int[] digits) {
        for (int i = digits.length - 1; i >= 0; i--) {
            if (digits[i] < 9) { digits[i]++; return digits; }
            digits[i] = 0;
        }
        int[] res = new int[digits.length + 1];
        res[0] = 1;
        return res;
    }
    
    public static void main(String[] args) {
        Problem28_PlusOne sol = new Problem28_PlusOne();
        System.out.println(Arrays.toString(sol.plusOne(new int[]{1, 2, 3}))); // [1,2,4]
        System.out.println(Arrays.toString(sol.plusOne(new int[]{9, 9, 9}))); // [1,0,0,0]
    }
}
