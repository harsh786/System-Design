import java.util.*;

/**
 * Problem 27: Longest Common Prefix (Trie approach)
 * 
 * Find the longest common prefix among an array of strings using a Trie.
 * Walk down trie while there's only one child and no word ends.
 * 
 * Time Complexity: O(n * m) to build, O(m) to find LCP
 * Space Complexity: O(n * m)
 * 
 * Production Analogy: DNS zone detection, common URL path extraction for routing,
 * shared library path detection in build systems.
 */
public class Problem27_LongestCommonPrefix {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEnd = false;
        int childCount = 0;
    }

    public static String longestCommonPrefix(String[] strs) {
        if (strs == null || strs.length == 0) return "";
        TrieNode root = new TrieNode();
        for (String s : strs) {
            if (s.isEmpty()) return "";
            TrieNode node = root;
            for (char c : s.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) {
                    node.children[idx] = new TrieNode();
                    node.childCount++;
                }
                node = node.children[idx];
            }
            node.isEnd = true;
        }

        StringBuilder sb = new StringBuilder();
        TrieNode node = root;
        while (node.childCount == 1 && !node.isEnd) {
            for (int i = 0; i < 26; i++) {
                if (node.children[i] != null) {
                    sb.append((char) ('a' + i));
                    node = node.children[i];
                    break;
                }
            }
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(longestCommonPrefix(new String[]{"flower","flow","flight"})); // "fl"
        System.out.println(longestCommonPrefix(new String[]{"dog","racecar","car"}));    // ""
        System.out.println(longestCommonPrefix(new String[]{"abc","abc","abc"}));        // "abc"
        System.out.println(longestCommonPrefix(new String[]{""}));                       // ""
        System.out.println(longestCommonPrefix(new String[]{"a"}));                      // "a"
    }
}
