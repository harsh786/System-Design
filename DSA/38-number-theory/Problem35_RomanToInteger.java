package numbertheory;

import java.util.*;

/**
 * Problem 35: Roman to Integer (LeetCode 13)
 * 
 * Approach: If current value < next value, subtract; else add.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 */
public class Problem35_RomanToInteger {
    
    public int romanToInt(String s) {
        Map<Character, Integer> map = Map.of('I',1,'V',5,'X',10,'L',50,'C',100,'D',500,'M',1000);
        int result = 0;
        for (int i = 0; i < s.length(); i++) {
            int cur = map.get(s.charAt(i));
            int next = (i + 1 < s.length()) ? map.get(s.charAt(i + 1)) : 0;
            result += (cur < next) ? -cur : cur;
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem35_RomanToInteger sol = new Problem35_RomanToInteger();
        System.out.println(sol.romanToInt("MCMXCIV")); // 1994
        System.out.println(sol.romanToInt("LVIII"));   // 58
    }
}
