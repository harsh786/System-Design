import java.util.*;

/**
 * Problem 17: Multiply Strings (LeetCode 43)
 * 
 * Multiply two non-negative integers represented as strings without using BigInteger.
 * 
 * Approach: Grade school multiplication. positions[i+j+1] += digit[i] * digit[j].
 * O(m*n) time, O(m+n) space.
 * 
 * Production Analogy: Like computing large financial transactions where numbers exceed
 * 64-bit precision - must use arbitrary precision arithmetic.
 */
public class Problem17_MultiplyStrings {

    public static String multiply(String num1, String num2) {
        int m = num1.length(), n = num2.length();
        int[] pos = new int[m + n];
        for (int i = m - 1; i >= 0; i--) {
            for (int j = n - 1; j >= 0; j--) {
                int mul = (num1.charAt(i) - '0') * (num2.charAt(j) - '0');
                int p1 = i + j, p2 = i + j + 1;
                int sum = mul + pos[p2];
                pos[p2] = sum % 10;
                pos[p1] += sum / 10;
            }
        }
        StringBuilder sb = new StringBuilder();
        for (int p : pos) if (!(sb.length() == 0 && p == 0)) sb.append(p);
        return sb.length() == 0 ? "0" : sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(multiply("2", "3"));     // "6"
        System.out.println(multiply("123", "456")); // "56088"
        System.out.println(multiply("0", "0"));     // "0"
        System.out.println(multiply("999", "999")); // "998001"
    }
}
