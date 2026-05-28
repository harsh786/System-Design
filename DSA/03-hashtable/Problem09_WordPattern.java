import java.util.*;

/**
 * Problem 9: Word Pattern
 * Check if a pattern string matches a space-separated string (bijection).
 *
 * Approach: Bidirectional HashMap mapping pattern char <-> word.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 *
 * Production Analogy: Template matching in log analysis - detecting if log entries
 * follow a structural pattern (like structured logging format validation).
 */
public class Problem09_WordPattern {
    public boolean wordPattern(String pattern, String s) {
        String[] words = s.split(" ");
        if (pattern.length() != words.length) return false;
        Map<Character, String> pToW = new HashMap<>();
        Map<String, Character> wToP = new HashMap<>();
        for (int i = 0; i < pattern.length(); i++) {
            char p = pattern.charAt(i);
            String w = words[i];
            if (pToW.containsKey(p) && !pToW.get(p).equals(w)) return false;
            if (wToP.containsKey(w) && wToP.get(w) != p) return false;
            pToW.put(p, w);
            wToP.put(w, p);
        }
        return true;
    }

    public static void main(String[] args) {
        Problem09_WordPattern sol = new Problem09_WordPattern();
        System.out.println(sol.wordPattern("abba", "dog cat cat dog")); // true
        System.out.println(sol.wordPattern("abba", "dog cat cat fish")); // false
        System.out.println(sol.wordPattern("aaaa", "dog cat cat dog")); // false
        System.out.println(sol.wordPattern("abba", "dog dog dog dog")); // false
    }
}
