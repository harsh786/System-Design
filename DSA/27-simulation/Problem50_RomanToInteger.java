/**
 * Problem: Roman to Integer (LeetCode 13) - Simulation approach
 * Approach: Scan left to right, subtract if current < next
 * Complexity: O(n) time, O(1) space
 * Production Analogy: Sequential parsing with lookahead in protocol decoders
 */
import java.util.*;
public class Problem50_RomanToInteger {
    public int romanToInt(String s) {
        Map<Character, Integer> map = Map.of('I',1,'V',5,'X',10,'L',50,'C',100,'D',500,'M',1000);
        int result = 0;
        for (int i = 0; i < s.length(); i++) {
            int cur = map.get(s.charAt(i));
            int next = (i+1 < s.length()) ? map.get(s.charAt(i+1)) : 0;
            result += (cur < next) ? -cur : cur;
        }
        return result;
    }
    public static void main(String[] args) {
        System.out.println(new Problem50_RomanToInteger().romanToInt("MCMXCIV")); // 1994
    }
}
