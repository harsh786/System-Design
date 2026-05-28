import java.util.*;

/**
 * Problem 8: Isomorphic Strings
 * Two strings are isomorphic if characters in s can be replaced to get t (one-to-one mapping).
 *
 * Approach: Two HashMaps for bidirectional mapping s->t and t->s.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(charset_size)
 *
 * Production Analogy: Like schema mapping between two different database systems.
 * Each field in source maps to exactly one field in target and vice versa.
 */
public class Problem08_IsomorphicStrings {
    public boolean isIsomorphic(String s, String t) {
        if (s.length() != t.length()) return false;
        Map<Character, Character> sToT = new HashMap<>(), tToS = new HashMap<>();
        for (int i = 0; i < s.length(); i++) {
            char sc = s.charAt(i), tc = t.charAt(i);
            if (sToT.containsKey(sc) && sToT.get(sc) != tc) return false;
            if (tToS.containsKey(tc) && tToS.get(tc) != sc) return false;
            sToT.put(sc, tc);
            tToS.put(tc, sc);
        }
        return true;
    }

    public static void main(String[] args) {
        Problem08_IsomorphicStrings sol = new Problem08_IsomorphicStrings();
        System.out.println(sol.isIsomorphic("egg", "add")); // true
        System.out.println(sol.isIsomorphic("foo", "bar")); // false
        System.out.println(sol.isIsomorphic("paper", "title")); // true
        System.out.println(sol.isIsomorphic("badc", "baba")); // false
    }
}
