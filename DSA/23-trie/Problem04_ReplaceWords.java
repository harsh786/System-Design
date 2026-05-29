import java.util.*;

/**
 * Problem 4: Replace Words
 * 
 * Given a dictionary of roots and a sentence, replace all successors in the sentence with the root.
 * A successor has the same prefix as the root.
 * 
 * Time Complexity: O(d*l + s*w) where d=dict size, l=avg root len, s=sentence words, w=avg word len
 * Space Complexity: O(d*l) for the trie
 * 
 * Production Analogy: Text normalization in NLP pipelines, stemming/lemmatization,
 * URL shorteners replacing long URLs with short prefixes.
 */
public class Problem04_ReplaceWords {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        String word = null;
    }

    public static String replaceWords(List<String> dictionary, String sentence) {
        TrieNode root = new TrieNode();
        for (String w : dictionary) {
            TrieNode node = root;
            for (char c : w.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
            }
            node.word = w;
        }

        StringBuilder sb = new StringBuilder();
        for (String word : sentence.split(" ")) {
            if (sb.length() > 0) sb.append(" ");
            TrieNode node = root;
            String replacement = word;
            for (char c : word.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) break;
                node = node.children[idx];
                if (node.word != null) { replacement = node.word; break; }
            }
            sb.append(replacement);
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(replaceWords(Arrays.asList("cat","bat","rat"),
            "the cattle was rattled by the battery"));
        // "the cat was rat by the bat"

        System.out.println(replaceWords(Arrays.asList("a","b","c"),
            "aadsfasf absbd bbab cadsfabd"));
        // "a a b c"

        System.out.println(replaceWords(Arrays.asList("catt","cat","bat"),
            "the cattle was rattled by the battery"));
        // "the cat was rattled by the bat" (shortest root wins)
    }
}
