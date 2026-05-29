/**
 * Problem: Find All Anagrams in a String (LeetCode 438)
 * Approach: Sliding window with frequency count
 * Complexity: O(n) time, O(1) space
 * Production Analogy: Pattern matching in network intrusion detection
 */
import java.util.*;
public class Problem11_FindAllAnagrams {
    public List<Integer> findAnagrams(String s, String p) {
        List<Integer> res = new ArrayList<>();
        if (s.length() < p.length()) return res;
        int[] count = new int[26];
        for (char c : p.toCharArray()) count[c-'a']++;
        int matched = 0;
        for (int i = 0; i < s.length(); i++) {
            if (--count[s.charAt(i)-'a'] >= 0) matched++;
            if (i >= p.length() && ++count[s.charAt(i-p.length())-'a'] > 0) matched--;
            if (matched == p.length()) res.add(i-p.length()+1);
        }
        return res;
    }
    public static void main(String[] args) {
        System.out.println(new Problem11_FindAllAnagrams().findAnagrams("cbaebabacd", "abc")); // [0,6]
    }
}
