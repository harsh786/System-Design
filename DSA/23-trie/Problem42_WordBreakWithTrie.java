import java.util.*;

/**
 * Problem 42: Word Break with Trie
 * 
 * Determine if a string can be segmented into space-separated dictionary words.
 * Trie-optimized version using DP + Trie prefix scanning.
 * 
 * Time Complexity: O(n * m) where n = string length, m = max word length in dict
 * Space Complexity: O(d * m) for trie + O(n) for DP
 * 
 * Production Analogy: URL slug validation, search query tokenization,
 * CamelCase splitting, compound word verification.
 */
public class Problem42_WordBreakWithTrie {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEnd = false;
    }

    public static boolean wordBreak(String s, List<String> wordDict) {
        TrieNode root = new TrieNode();
        for (String w : wordDict) {
            TrieNode node = root;
            for (char c : w.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
            }
            node.isEnd = true;
        }

        boolean[] dp = new boolean[s.length() + 1];
        dp[0] = true;

        for (int i = 0; i < s.length(); i++) {
            if (!dp[i]) continue;
            TrieNode node = root;
            for (int j = i; j < s.length(); j++) {
                int idx = s.charAt(j) - 'a';
                if (node.children[idx] == null) break;
                node = node.children[idx];
                if (node.isEnd) dp[j + 1] = true;
            }
        }
        return dp[s.length()];
    }

    public static void main(String[] args) {
        System.out.println(wordBreak("leetcode", Arrays.asList("leet","code")));    // true
        System.out.println(wordBreak("applepenapple", Arrays.asList("apple","pen")));// true
        System.out.println(wordBreak("catsandog", Arrays.asList("cats","dog","sand","and","cat"))); // false
        System.out.println(wordBreak("aaaaaaa", Arrays.asList("aaa","aaaa")));      // true
    }
}
