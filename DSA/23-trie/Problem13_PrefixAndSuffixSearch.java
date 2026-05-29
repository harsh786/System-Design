import java.util.*;

/**
 * Problem 13: Prefix and Suffix Search
 * 
 * Design a data structure that supports searching words by prefix AND suffix simultaneously.
 * Trick: Insert word as "suffix#word" for all suffixes combined with the word.
 * 
 * Time Complexity: O(n * k^2) to build, O(m) to query
 * Space Complexity: O(n * k^2)
 * 
 * Production Analogy: File extension + prefix search (find all "test*.java"),
 * email filtering (from:*@domain.com with subject:prefix*).
 */
public class Problem13_PrefixAndSuffixSearch {

    static class TrieNode {
        TrieNode[] children = new TrieNode[27]; // 26 letters + '#'
        int weight = -1;
    }

    static class WordFilter {
        TrieNode root = new TrieNode();

        public WordFilter(String[] words) {
            for (int w = 0; w < words.length; w++) {
                String word = words[w];
                // Insert all combinations: suffix + '#' + word
                for (int i = 0; i <= word.length(); i++) {
                    String key = word.substring(i) + "#" + word;
                    TrieNode node = root;
                    for (char c : key.toCharArray()) {
                        int idx = (c == '#') ? 26 : c - 'a';
                        if (node.children[idx] == null) node.children[idx] = new TrieNode();
                        node = node.children[idx];
                        node.weight = w;
                    }
                }
            }
        }

        public int f(String prefix, String suffix) {
            String key = suffix + "#" + prefix;
            TrieNode node = root;
            for (char c : key.toCharArray()) {
                int idx = (c == '#') ? 26 : c - 'a';
                if (node.children[idx] == null) return -1;
                node = node.children[idx];
            }
            return node.weight;
        }
    }

    public static void main(String[] args) {
        WordFilter wf = new WordFilter(new String[]{"apple","app","maple"});
        System.out.println(wf.f("a", "e"));    // 0 (apple)
        System.out.println(wf.f("ap", "le"));  // 2 (maple? no - apple idx 0, maple idx 2)
        System.out.println(wf.f("ma", "le"));  // 2 (maple)
        System.out.println(wf.f("app", "pp")); // -1? let's check: no word with prefix "app" and suffix "pp" -> wait "app" has suffix "pp"? -> no "app" ends in "pp"? no, "app" suffix is "p","pp","app" -> idx 1
        System.out.println(wf.f("b", "e"));    // -1
    }
}
