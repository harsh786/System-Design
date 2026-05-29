import java.util.*;

/**
 * Problem 24: Sum of Prefix Scores of Strings
 * 
 * For each word, compute the sum of scores of all its prefixes.
 * Score of a prefix = number of words in the array that have this prefix.
 * 
 * Time Complexity: O(n * m) where n = words, m = max length
 * Space Complexity: O(n * m)
 * 
 * Production Analogy: Search relevance scoring (how many documents match each prefix),
 * popularity metrics in autocomplete systems, prefix-based analytics.
 */
public class Problem24_SumOfPrefixScores {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        int prefixCount = 0;
    }

    public static int[] sumPrefixScores(String[] words) {
        TrieNode root = new TrieNode();
        for (String w : words) {
            TrieNode node = root;
            for (char c : w.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
                node.prefixCount++;
            }
        }

        int[] result = new int[words.length];
        for (int i = 0; i < words.length; i++) {
            TrieNode node = root;
            int score = 0;
            for (char c : words[i].toCharArray()) {
                node = node.children[c - 'a'];
                score += node.prefixCount;
            }
            result[i] = score;
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(sumPrefixScores(new String[]{"abc","ab","bc","b"})));
        // [5, 4, 3, 2] -> "abc": a(2)+ab(2)+abc(1)=5, "ab": a(2)+ab(2)=4, "bc": b(2)+bc(1)=3, "b": b(2)=2
        System.out.println(Arrays.toString(sumPrefixScores(new String[]{"abcd"})));
        // [4]
    }
}
