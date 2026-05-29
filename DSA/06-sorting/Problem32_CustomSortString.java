import java.util.*;

/**
 * Problem 32: Custom Sort String
 * 
 * Given order string and string s, sort s according to order defined by order string.
 * 
 * Approach: Count chars in s, output in order sequence, then remaining.
 * Time Complexity: O(n + m)
 * Space Complexity: O(26) = O(1)
 * 
 * Production Analogy: Custom column ordering in report generation based on user preferences.
 */
public class Problem32_CustomSortString {
    
    public String customSortString(String order, String s) {
        int[] count = new int[26];
        for (char c : s.toCharArray()) count[c - 'a']++;
        
        StringBuilder sb = new StringBuilder();
        for (char c : order.toCharArray()) {
            while (count[c - 'a']-- > 0) sb.append(c);
        }
        for (int i = 0; i < 26; i++) {
            while (count[i]-- > 0) sb.append((char)('a' + i));
        }
        return sb.toString();
    }
    
    public static void main(String[] args) {
        Problem32_CustomSortString sol = new Problem32_CustomSortString();
        
        System.out.println("Test 1: " + sol.customSortString("cba", "abcd")); // "cbad"
        System.out.println("Test 2: " + sol.customSortString("bcafg", "abcd")); // "bcad"
        System.out.println("Test 3: " + sol.customSortString("kqep", "pekeq")); // "kqeep"
    }
}
