import java.util.*;

/**
 * Problem 36: Word Pattern (LeetCode 290)
 * 
 * Approach: Bijective mapping between pattern chars and words. O(n) time, O(n) space.
 * 
 * Production Analogy: Like validating that a URL pattern template matches actual routes
 * consistently (e.g., /user/:id must always map :id to same type).
 */
public class Problem36_WordPattern {

    public static boolean wordPattern(String pattern, String s) {
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
        System.out.println(wordPattern("abba", "dog cat cat dog")); // true
        System.out.println(wordPattern("abba", "dog cat cat fish")); // false
        System.out.println(wordPattern("aaaa", "dog cat cat dog")); // false
    }
}
