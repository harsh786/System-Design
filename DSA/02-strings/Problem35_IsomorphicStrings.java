import java.util.*;

/**
 * Problem 35: Isomorphic Strings (LeetCode 205)
 * 
 * Approach: Map each char in s to t and vice versa. O(n) time, O(1) space.
 * 
 * Production Analogy: Like verifying two API schemas have the same structure with
 * consistent field renaming (bijective mapping).
 */
public class Problem35_IsomorphicStrings {

    public static boolean isIsomorphic(String s, String t) {
        int[] mapS = new int[256], mapT = new int[256];
        for (int i = 0; i < s.length(); i++) {
            if (mapS[s.charAt(i)] != mapT[t.charAt(i)]) return false;
            mapS[s.charAt(i)] = i + 1;
            mapT[t.charAt(i)] = i + 1;
        }
        return true;
    }

    public static void main(String[] args) {
        System.out.println(isIsomorphic("egg", "add"));     // true
        System.out.println(isIsomorphic("foo", "bar"));     // false
        System.out.println(isIsomorphic("paper", "title")); // true
        System.out.println(isIsomorphic("badc", "baba"));   // false
    }
}
