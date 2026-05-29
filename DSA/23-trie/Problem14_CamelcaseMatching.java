import java.util.*;

/**
 * Problem 14: Camelcase Matching
 * 
 * Given queries and a pattern, determine if each query matches the pattern.
 * A query matches if we can insert lowercase letters into pattern to get the query.
 * 
 * Time Complexity: O(n * m) where n = queries, m = max query length
 * Space Complexity: O(1) extra (or O(pattern) for trie approach)
 * 
 * Production Analogy: IDE symbol search (typing "NPE" finds "NullPointerException"),
 * CamelCase navigation in IntelliJ/VSCode, class name filtering.
 */
public class Problem14_CamelcaseMatching {

    static class TrieNode {
        TrieNode[] children = new TrieNode[128]; // ASCII
        boolean isEnd = false;
    }

    public static List<Boolean> camelMatch(String[] queries, String pattern) {
        List<Boolean> result = new ArrayList<>();
        for (String query : queries) {
            result.add(matches(query, pattern));
        }
        return result;
    }

    static boolean matches(String query, String pattern) {
        int j = 0;
        for (int i = 0; i < query.length(); i++) {
            char c = query.charAt(i);
            if (j < pattern.length() && c == pattern.charAt(j)) {
                j++;
            } else if (Character.isUpperCase(c)) {
                return false; // unmatched uppercase
            }
        }
        return j == pattern.length();
    }

    public static void main(String[] args) {
        System.out.println(camelMatch(
            new String[]{"FooBar","FooBarTest","FootBall","FrameBuffer","ForceFeedBack"},
            "FB")); // [true, false, true, true, false]

        System.out.println(camelMatch(
            new String[]{"FooBar","FooBarTest","FootBall","FrameBuffer","ForceFeedBack"},
            "FoBa")); // [true, false, true, false, false]

        System.out.println(camelMatch(
            new String[]{"FooBar","FooBarTest","FootBall","FrameBuffer","ForceFeedBack"},
            "FoBaT")); // [false, true, false, false, false]
    }
}
