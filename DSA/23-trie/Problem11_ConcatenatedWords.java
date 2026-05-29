import java.util.*;

/**
 * Problem 11: Concatenated Words
 * 
 * Find all words that can be formed by concatenating at least 2 shorter words from the array.
 * 
 * Time Complexity: O(n * m^2) where n = words count, m = max word length
 * Space Complexity: O(n * m) for trie
 * 
 * Production Analogy: Compound word detection in NLP, domain name validation
 * (sub.domain.tld), URL path segment validation.
 */
public class Problem11_ConcatenatedWords {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEnd = false;
    }

    static TrieNode root;

    public static List<String> findAllConcatenatedWordsInADict(String[] words) {
        root = new TrieNode();
        Arrays.sort(words, (a, b) -> a.length() - b.length());
        List<String> result = new ArrayList<>();

        for (String word : words) {
            if (word.isEmpty()) continue;
            if (canForm(word, 0)) {
                result.add(word);
            }
            // Insert into trie
            TrieNode node = root;
            for (char c : word.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
            }
            node.isEnd = true;
        }
        return result;
    }

    static boolean canForm(String word, int start) {
        if (start == word.length()) return true;
        TrieNode node = root;
        for (int i = start; i < word.length(); i++) {
            int idx = word.charAt(i) - 'a';
            if (node.children[idx] == null) return false;
            node = node.children[idx];
            if (node.isEnd && canForm(word, i + 1)) return true;
        }
        return false;
    }

    public static void main(String[] args) {
        System.out.println(findAllConcatenatedWordsInADict(new String[]{
            "cat","cats","catsdogcats","dog","dogcatsdog","hippopotamuses","rat","ratcatdogcat"
        })); // [catsdogcats, dogcatsdog, ratcatdogcat]

        System.out.println(findAllConcatenatedWordsInADict(new String[]{"cat","dog","catdog"}));
        // [catdog]
    }
}
