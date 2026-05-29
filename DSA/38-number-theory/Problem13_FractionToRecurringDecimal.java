package numbertheory;

import java.util.*;

/**
 * Problem 13: Fraction to Recurring Decimal (LeetCode 166)
 * 
 * Approach: Long division tracking remainders to detect cycle.
 * 
 * Time Complexity: O(denominator) worst case
 * Space Complexity: O(denominator)
 */
public class Problem13_FractionToRecurringDecimal {
    
    public String fractionToDecimal(int numerator, int denominator) {
        if (numerator == 0) return "0";
        StringBuilder sb = new StringBuilder();
        if ((numerator < 0) ^ (denominator < 0)) sb.append('-');
        long num = Math.abs((long) numerator), den = Math.abs((long) denominator);
        sb.append(num / den);
        long rem = num % den;
        if (rem == 0) return sb.toString();
        sb.append('.');
        Map<Long, Integer> map = new HashMap<>();
        while (rem != 0) {
            if (map.containsKey(rem)) {
                sb.insert(map.get(rem), "(");
                sb.append(')');
                break;
            }
            map.put(rem, sb.length());
            rem *= 10;
            sb.append(rem / den);
            rem %= den;
        }
        return sb.toString();
    }
    
    public static void main(String[] args) {
        Problem13_FractionToRecurringDecimal sol = new Problem13_FractionToRecurringDecimal();
        System.out.println(sol.fractionToDecimal(1, 3));  // 0.(3)
        System.out.println(sol.fractionToDecimal(4, 333)); // 0.(012)
    }
}
