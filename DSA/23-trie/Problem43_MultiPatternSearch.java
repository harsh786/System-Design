import java.util.*;

/**
 * Problem 43: Multi-pattern Search with Trie (Aho-Corasick simplified)
 * 
 * Given a text and multiple patterns, find all pattern occurrences in the text.
 * Build trie of patterns, then scan text character by character.
 * 
 * Time Complexity: O(text_len * max_pattern_len + total_pattern_chars)
 * Space Complexity: O(total_pattern_chars)
 * 
 * Production Analogy: Antivirus signature scanning, content filtering (profanity detection),
 * network intrusion detection (Snort), log pattern matching (grep -f patterns.txt).
 */
public class Problem43_MultiPatternSearch {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        List<String> outputs = new ArrayList<>(); // patterns ending here
    }

    public static Map<String, List<Integer>> multiSearch(String text, String[] patterns) {
        TrieNode root = new TrieNode();
        for (String p : patterns) {
            TrieNode node = root;
            for (char c : p.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
            }
            node.outputs.add(p);
        }

        Map<String, List<Integer>> result = new HashMap<>();
        for (String p : patterns) result.put(p, new ArrayList<>());

        // For each starting position, try to match patterns via trie
        for (int i = 0; i < text.length(); i++) {
            TrieNode node = root;
            for (int j = i; j < text.length(); j++) {
                int idx = text.charAt(j) - 'a';
                if (node.children[idx] == null) break;
                node = node.children[idx];
                for (String match : node.outputs) {
                    result.get(match).add(i);
                }
            }
        }
        return result;
    }

    public static void main(String[] args) {
        String text = "abcabcabc";
        String[] patterns = {"abc", "bc", "cab"};
        Map<String, List<Integer>> result = multiSearch(text, patterns);
        for (Map.Entry<String, List<Integer>> e : result.entrySet()) {
            System.out.println(e.getKey() + " -> " + e.getValue());
        }
        // abc -> [0, 3, 6], bc -> [1, 4, 7], cab -> [2, 5]

        System.out.println("---");
        String text2 = "thequickbrownfox";
        String[] patterns2 = {"quick", "brown", "fox", "ox"};
        Map<String, List<Integer>> result2 = multiSearch(text2, patterns2);
        for (Map.Entry<String, List<Integer>> e : result2.entrySet()) {
            System.out.println(e.getKey() + " -> " + e.getValue());
        }
    }
}
