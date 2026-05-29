/**
 * Problem: Custom Sort String (LeetCode 791) - Counting approach
 * Approach: Count chars in s, output in order specified, then remainder
 * Complexity: O(n + m) time, O(1) space
 * Production Analogy: Custom ordering in display/presentation layers
 */
public class Problem49_CustomSortString {
    public String customSortString(String order, String s) {
        int[] count = new int[26];
        for (char c : s.toCharArray()) count[c-'a']++;
        StringBuilder sb = new StringBuilder();
        for (char c : order.toCharArray()) { while (count[c-'a']-- > 0) sb.append(c); }
        for (int i = 0; i < 26; i++) while (count[i]-- > 0) sb.append((char)('a'+i));
        return sb.toString();
    }
    public static void main(String[] args) {
        System.out.println(new Problem49_CustomSortString().customSortString("cba", "abcd")); // cbad
    }
}
