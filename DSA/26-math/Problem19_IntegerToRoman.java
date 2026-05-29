/**
 * Problem 19: Integer to Roman
 * Convert integer (1-3999) to Roman numeral string.
 *
 * Approach: Greedy - subtract largest possible Roman value repeatedly.
 * Time Complexity: O(1) - bounded input range
 * Space Complexity: O(1)
 *
 * Production Analogy: Like encoding values into a fixed vocabulary of symbols,
 * similar to variable-length encoding in compression algorithms.
 */
public class Problem19_IntegerToRoman {

    public static String intToRoman(int num) {
        int[] values =    {1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1};
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
        System.out.println(intToRoman(3));     // "III"
        System.out.println(intToRoman(58));    // "LVIII"
        System.out.println(intToRoman(1994));  // "MCMXCIV"
        System.out.println(intToRoman(3999));  // "MMMCMXCIX"
    }
}
