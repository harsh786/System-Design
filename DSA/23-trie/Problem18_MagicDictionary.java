import java.util.*;

/**
 * Problem 18: Implement Magic Dictionary
 * 
 * Build a dictionary, then search if a word can be formed by changing exactly one character.
 * 
 * Time Complexity: Build O(n*m), Search O(26*m) = O(m)
 * Space Complexity: O(n*m)
 * 
 * Production Analogy: Spell checker "Did you mean?" suggestions,
 * fuzzy matching in search engines, typo tolerance in Elasticsearch.
 */
public class Problem18_MagicDictionary {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEnd = false;
    }

    static class MagicDictionary {
        TrieNode root = new TrieNode();

        public void buildDict(String[] dictionary) {
            for (String w : dictionary) {
                TrieNode node = root;
                for (char c : w.toCharArray()) {
                    int idx = c - 'a';
                    if (node.children[idx] == null) node.children[idx] = new TrieNode();
                    node = node.children[idx];
                }
                node.isEnd = true;
            }
        }

        public boolean search(String searchWord) {
            return dfs(searchWord, 0, root, false);
        }

        boolean dfs(String word, int i, TrieNode node, boolean changed) {
            if (i == word.length()) return node.isEnd && changed;
            int idx = word.charAt(i) - 'a';
            if (changed) {
                if (node.children[idx] == null) return false;
                return dfs(word, i + 1, node.children[idx], true);
            }
            for (int c = 0; c < 26; c++) {
                if (node.children[c] == null) continue;
                if (c == idx) {
                    if (dfs(word, i + 1, node.children[c], false)) return true;
                } else {
                    if (dfs(word, i + 1, node.children[c], true)) return true;
                }
            }
            return false;
        }
    }

    public static void main(String[] args) {
        MagicDictionary md = new MagicDictionary();
        md.buildDict(new String[]{"hello", "leetcode"});
        System.out.println(md.search("hello"));    // false (0 changes)
        System.out.println(md.search("hhllo"));    // true (change e->h)
        System.out.println(md.search("hell"));     // false (different length)
        System.out.println(md.search("leetcoded"));// false
        System.out.println(md.search("leetcodd")); // false? "leetcode" vs "leetcodd" -> change e->d at pos 7 -> true? No, lengths differ
    }
}
