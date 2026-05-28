import java.util.*;

/**
 * Problem 15: Integer to Roman (LeetCode 12)
 * 
 * Approach: Greedy - use value table from largest to smallest. O(1) time/space (bounded input).
 * 
 * Production Analogy: Like making change with coins - always pick the largest denomination first.
 */
public class Problem15_IntegerToRoman {

    public static String intToRoman(int num) {
        int[] values = {1000,900,500,400,100,90,50,40,10,9,5,4,1};
        String[] symbols = {"M","CM","D","CD","C","XC","L","XL","X","IX","V","IV","I"};
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < values.length; i++) {
            while (num >= values[i]) {
                sb.append(symbols[i]);
                num -= values[i];
            }
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(intToRoman(3));    // "III"
        System.out.println(intToRoman(58));   // "LVIII"
        System.out.println(intToRoman(1994)); // "MCMXCIV"
        System.out.println(intToRoman(3999)); // "MMMCMXCIX"
    }
}
