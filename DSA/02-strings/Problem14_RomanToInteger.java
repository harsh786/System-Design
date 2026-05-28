import java.util.*;

/**
 * Problem 14: Roman to Integer (LeetCode 13)
 * 
 * Approach: If current value < next value, subtract; otherwise add. O(n) time, O(1) space.
 * 
 * Production Analogy: Like parsing version strings with special precedence rules.
 */
public class Problem14_RomanToInteger {

    public static int romanToInt(String s) {
        Map<Character, Integer> map = Map.of('I',1,'V',5,'X',10,'L',50,'C',100,'D',500,'M',1000);
        int result = 0;
        for (int i = 0; i < s.length(); i++) {
            if (i + 1 < s.length() && map.get(s.charAt(i)) < map.get(s.charAt(i + 1))) {
                result -= map.get(s.charAt(i));
            } else {
                result += map.get(s.charAt(i));
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(romanToInt("III"));     // 3
        System.out.println(romanToInt("LVIII"));   // 58
        System.out.println(romanToInt("MCMXCIV")); // 1994
        System.out.println(romanToInt("IV"));      // 4
    }
}
