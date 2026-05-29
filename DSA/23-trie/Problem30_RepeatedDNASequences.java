import java.util.*;

/**
 * Problem 30: Trie for Repeated DNA Sequences
 * 
 * Find all 10-letter-long sequences that occur more than once in a DNA string.
 * Using trie with only 4 children (A,C,G,T).
 * 
 * Time Complexity: O(n * 10) where n = string length
 * Space Complexity: O(n * 10) worst case for trie
 * 
 * Production Analogy: Genome sequence analysis, pattern detection in biological data,
 * plagiarism detection (finding repeated text fragments).
 */
public class Problem30_RepeatedDNASequences {

    static class TrieNode {
        TrieNode[] children = new TrieNode[4]; // A=0, C=1, G=2, T=3
        int count = 0;
    }

    static int charToIdx(char c) {
        switch(c) { case 'A': return 0; case 'C': return 1; case 'G': return 2; default: return 3; }
    }

    public static List<String> findRepeatedDnaSequences(String s) {
        if (s.length() <= 10) return new ArrayList<>();
        TrieNode root = new TrieNode();
        List<String> result = new ArrayList<>();

        for (int i = 0; i <= s.length() - 10; i++) {
            TrieNode node = root;
            for (int j = i; j < i + 10; j++) {
                int idx = charToIdx(s.charAt(j));
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
            }
            node.count++;
            if (node.count == 2) result.add(s.substring(i, i + 10));
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(findRepeatedDnaSequences("AAAAACCCCCAAAAACCCCCCAAAAAGGGTTT"));
        // [AAAAACCCCC, CCCCCAAAAA]
        System.out.println(findRepeatedDnaSequences("AAAAAAAAAAAAA"));
        // [AAAAAAAAAA]
        System.out.println(findRepeatedDnaSequences("AAAAAAAAAAA"));
        // [AAAAAAAAAA]
    }
}
