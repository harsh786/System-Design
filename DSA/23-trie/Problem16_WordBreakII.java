import java.util.*;

/**
 * Problem 16: Word Break II (Trie approach)
 * 
 * Given a string and dictionary, return all possible sentences formed by breaking the string.
 * 
 * Time Complexity: O(2^n) worst case, O(n^2 * m) with memoization
 * Space Complexity: O(n * m) for trie + O(n * results) for output
 * 
 * Production Analogy: Chinese/Japanese word segmentation, hashtag parsing (#ThrowbackThursday),
 * domain name segmentation (stackoverflowquestions -> stack overflow questions).
 */
public class Problem16_WordBreakII {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEnd = false;
    }

    public static List<String> wordBreak(String s, List<String> wordDict) {
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
        Map<Integer, List<String>> memo = new HashMap<>();
        return dfs(s, 0, root, memo);
    }

    static List<String> dfs(String s, int start, TrieNode root, Map<Integer, List<String>> memo) {
        if (memo.containsKey(start)) return memo.get(start);
        List<String> result = new ArrayList<>();
        if (start == s.length()) { result.add(""); return result; }
        TrieNode node = root;
        for (int i = start; i < s.length(); i++) {
            int idx = s.charAt(i) - 'a';
            if (node.children[idx] == null) break;
            node = node.children[idx];
            if (node.isEnd) {
                String word = s.substring(start, i + 1);
                for (String rest : dfs(s, i + 1, root, memo)) {
                    result.add(rest.isEmpty() ? word : word + " " + rest);
                }
            }
        }
        memo.put(start, result);
        return result;
    }

    public static void main(String[] args) {
        System.out.println(wordBreak("catsanddog", Arrays.asList("cat","cats","and","sand","dog")));
        // [cats and dog, cat sand dog]
        System.out.println(wordBreak("pineapplepenapple", Arrays.asList("apple","pen","applepen","pine","pineapple")));
        System.out.println(wordBreak("catsandog", Arrays.asList("cats","dog","sand","and","cat")));
        // []
    }
}
