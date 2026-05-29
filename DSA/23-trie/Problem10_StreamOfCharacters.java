import java.util.*;

/**
 * Problem 10: Stream of Characters
 * 
 * Implement StreamChecker: given a list of words, for each character queried,
 * return true if some suffix of the queried characters so far equals a word.
 * 
 * Key Insight: Insert words in REVERSE into trie. Match stream buffer from end.
 * 
 * Time Complexity: O(m) per query where m = max word length
 * Space Complexity: O(n*m) for trie + O(maxLen) for buffer
 * 
 * Production Analogy: Real-time log monitoring (detecting error patterns as they stream in),
 * intrusion detection systems matching attack signatures in network packets.
 */
public class Problem10_StreamOfCharacters {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEnd = false;
    }

    static class StreamChecker {
        TrieNode root = new TrieNode();
        StringBuilder stream = new StringBuilder();
        int maxLen = 0;

        public StreamChecker(String[] words) {
            for (String w : words) {
                maxLen = Math.max(maxLen, w.length());
                TrieNode node = root;
                for (int i = w.length() - 1; i >= 0; i--) {
                    int idx = w.charAt(i) - 'a';
                    if (node.children[idx] == null) node.children[idx] = new TrieNode();
                    node = node.children[idx];
                }
                node.isEnd = true;
            }
        }

        public boolean query(char letter) {
            stream.append(letter);
            TrieNode node = root;
            for (int i = stream.length() - 1; i >= Math.max(0, stream.length() - maxLen); i--) {
                int idx = stream.charAt(i) - 'a';
                if (node.children[idx] == null) return false;
                node = node.children[idx];
                if (node.isEnd) return true;
            }
            return false;
        }
    }

    public static void main(String[] args) {
        StreamChecker sc = new StreamChecker(new String[]{"cd","f","kl"});
        System.out.println(sc.query('a')); // false
        System.out.println(sc.query('b')); // false
        System.out.println(sc.query('c')); // false
        System.out.println(sc.query('d')); // true (cd)
        System.out.println(sc.query('e')); // false
        System.out.println(sc.query('f')); // true (f)
        System.out.println(sc.query('g')); // false
        System.out.println(sc.query('h')); // false
        System.out.println(sc.query('i')); // false
        System.out.println(sc.query('j')); // false
        System.out.println(sc.query('k')); // false
        System.out.println(sc.query('l')); // true (kl)
    }
}
