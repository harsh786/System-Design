/**
 * Problem 20: Roman to Integer
 * Convert Roman numeral string to integer.
 *
 * Approach: If current value < next value, subtract; otherwise add.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like parsing legacy encoding formats where symbol
 * context determines interpretation (prefix vs standalone).
 */
import java.util.Map;

public class Problem20_RomanToInteger {

    public static int romanToInt(String s) {
        Map<Character, Integer> map = Map.of(
            'I', 1, 'V', 5, 'X', 10, 'L', 50,
            'C', 100, 'D', 500, 'M', 1000);

        int result = 0;
        for (int i = 0; i < s.length(); i++) {
            int val = map.get(s.charAt(i));
            if (i + 1 < s.length() && val < map.get(s.charAt(i + 1)))
                result -= val;
            else
                result += val;
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(romanToInt("III"));      // 3
        System.out.println(romanToInt("LVIII"));    // 58
        System.out.println(romanToInt("MCMXCIV")); // 1994
        System.out.println(romanToInt("MMMCMXCIX")); // 3999
    }
}
