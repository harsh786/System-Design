import java.util.*;

/**
 * Problem 19: Longest Word With All Prefixes
 * 
 * Find the longest word where every prefix of that word is also in the dictionary.
 * Same as Problem 6 but with different approach (sort + trie validation).
 * 
 * Time Complexity: O(n * m * log n) with sorting
 * Space Complexity: O(n * m)
 * 
 * Production Analogy: Progressive loading validation (each step must be valid),
 * incremental deployment pipelines, blockchain validation (each block depends on previous).
 */
public class Problem19_LongestWordWithAllPrefixes {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEnd = false;
    }

    public static String longestWordWithAllPrefixes(String[] words) {
        TrieNode root = new TrieNode();
        // Insert all words
        for (String w : words) {
            TrieNode node = root;
            for (char c : w.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
            }
            node.isEnd = true;
        }

        String result = "";
        for (String w : words) {
            if (w.length() < result.length()) continue;
            if (w.length() == result.length() && w.compareTo(result) >= 0) continue;
            // Check all prefixes exist
            TrieNode node = root;
            boolean valid = true;
            for (char c : w.toCharArray()) {
                node = node.children[c - 'a'];
                if (!node.isEnd) { valid = false; break; }
            }
            if (valid) result = w;
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(longestWordWithAllPrefixes(new String[]{"a","app","ap","appl","apple","apply","b"}));
        // "apple" (a->ap->app->appl->apple all exist)
        System.out.println(longestWordWithAllPrefixes(new String[]{"abc","bc","ab","a"}));
        // "abc" if "ab" and "a" exist -> yes! a->ab->abc
        System.out.println(longestWordWithAllPrefixes(new String[]{"z","zx","zxy","zxyw"}));
        // "zxyw"
    }
}
