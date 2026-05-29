import java.util.*;

/**
 * Problem 17: Short Encoding of Words
 * 
 * Find the minimum length encoding string such that every word in the array is a suffix
 * of some word in the encoding (words separated by '#').
 * Key insight: Words that are suffixes of other words don't need separate entries.
 * 
 * Time Complexity: O(n * m) where n = words, m = max length
 * Space Complexity: O(n * m)
 * 
 * Production Analogy: Data compression (suffix-based deduplication), 
 * DNS zone file optimization, string interning in JVM.
 */
public class Problem17_ShortEncodingOfWords {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        int depth = 0;
    }

    public static int minimumLengthEncoding(String[] words) {
        // Insert reversed words; leaves represent words that aren't suffixes of others
        TrieNode root = new TrieNode();
        Set<String> unique = new HashSet<>(Arrays.asList(words));
        Map<TrieNode, Integer> leaves = new HashMap<>();

        for (String word : unique) {
            TrieNode node = root;
            for (int i = word.length() - 1; i >= 0; i--) {
                int idx = word.charAt(i) - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
            }
            leaves.put(node, word.length());
        }

        int result = 0;
        for (Map.Entry<TrieNode, Integer> e : leaves.entrySet()) {
            // Check if this node is a leaf (no children)
            boolean isLeaf = true;
            for (TrieNode child : e.getKey().children) {
                if (child != null) { isLeaf = false; break; }
            }
            if (isLeaf) result += e.getValue() + 1; // +1 for '#'
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(minimumLengthEncoding(new String[]{"time","me","bell"})); // 10 ("time#bell#")
        System.out.println(minimumLengthEncoding(new String[]{"t"})); // 2
        System.out.println(minimumLengthEncoding(new String[]{"me","time"})); // 5 ("time#")
    }
}
