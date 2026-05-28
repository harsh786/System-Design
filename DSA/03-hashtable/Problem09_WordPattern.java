import java.util.*;

/**
 * Problem 9: Word Pattern
 * Given a pattern and a string s, find if s follows the same pattern.
 * pattern = "abba", s = "dog cat cat dog" -> true
 *
 * Approach: Bijective mapping between pattern chars and words using two HashMaps.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 *
 * Production Analogy: Like URL route pattern matching in web frameworks.
 * "/users/:id/posts/:id" must have consistent param bindings.
 */
public class Problem09_WordPattern {
    public boolean wordPattern(String pattern, String s) {
        String[] words = s.split(" ");
        if (pattern.length() != words.length) return false;
        Map<Character, String> pToW = new HashMap<>();
        Map<String, Character> wToP = new HashMap<>();
        for (int i = 0; i < pattern.length(); i++) {
            char c = pattern.charAt(i);
            String w = words[i];
            if (pToW.containsKey(c) && !pToW.get(c).equals(w)) return false;
            if (wToP.containsKey(w) && wToP.get(w) != c) return false;
            pToW.put(c, w);
            wToP.put(w, c);
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
