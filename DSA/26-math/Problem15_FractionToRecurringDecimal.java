/**
 * Problem 15: Fraction to Recurring Decimal
 * Convert fraction to string with recurring part in parentheses.
 *
 * Approach: Long division simulation. Track remainders to detect cycle.
 * Time Complexity: O(denominator) worst case
 * Space Complexity: O(denominator)
 *
 * Production Analogy: Like detecting periodic patterns in time-series data
 * or recurring billing cycle calculations.
 */
import java.util.HashMap;
import java.util.Map;

public class Problem15_FractionToRecurringDecimal {

    public static String fractionToDecimal(int numerator, int denominator) {
        if (numerator == 0) return "0";
        StringBuilder sb = new StringBuilder();

        if ((numerator < 0) ^ (denominator < 0)) sb.append('-');

        long num = Math.abs((long) numerator);
        long den = Math.abs((long) denominator);

        sb.append(num / den);
        long remainder = num % den;
        if (remainder == 0) return sb.toString();

        sb.append('.');
        Map<Long, Integer> map = new HashMap<>();

        while (remainder != 0) {
            if (map.containsKey(remainder)) {
                sb.insert(map.get(remainder), "(");
                sb.append(")");
                break;
            }
            map.put(remainder, sb.length());
            remainder *= 10;
            sb.append(remainder / den);
            remainder %= den;
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(fractionToDecimal(1, 2));    // "0.5"
        System.out.println(fractionToDecimal(2, 1));    // "2"
        System.out.println(fractionToDecimal(4, 333));  // "0.(012)"
        System.out.println(fractionToDecimal(1, 3));    // "0.(3)"
        System.out.println(fractionToDecimal(-50, 8));  // "-6.25"
        System.out.println(fractionToDecimal(Integer.MIN_VALUE, -1)); // "2147483648"
    }
}
