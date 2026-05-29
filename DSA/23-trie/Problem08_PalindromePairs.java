import java.util.*;

/**
 * Problem 8: Palindrome Pairs
 * 
 * Given a list of unique words, find all pairs (i,j) such that words[i]+words[j] is a palindrome.
 * 
 * Time Complexity: O(n * k^2) where n = number of words, k = max word length
 * Space Complexity: O(n * k) for trie
 * 
 * Production Analogy: Natural language processing for detecting symmetry patterns,
 * DNA sequence analysis for complementary strands.
 */
public class Problem08_PalindromePairs {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        int wordIndex = -1;
        List<Integer> palindromeSuffixes = new ArrayList<>();
    }

    static TrieNode root = new TrieNode();

    static void insert(String word, int index) {
        TrieNode node = root;
        for (int i = word.length() - 1; i >= 0; i--) {
            if (isPalindrome(word, 0, i)) node.palindromeSuffixes.add(index);
            int idx = word.charAt(i) - 'a';
            if (node.children[idx] == null) node.children[idx] = new TrieNode();
            node = node.children[idx];
        }
        node.wordIndex = index;
        node.palindromeSuffixes.add(index);
    }

    static boolean isPalindrome(String s, int l, int r) {
        while (l < r) { if (s.charAt(l++) != s.charAt(r--)) return false; }
        return true;
    }

    public static List<List<Integer>> palindromePairs(String[] words) {
        root = new TrieNode();
        List<List<Integer>> result = new ArrayList<>();
        for (int i = 0; i < words.length; i++) insert(words[i], i);

        for (int i = 0; i < words.length; i++) {
            String word = words[i];
            TrieNode node = root;
            for (int j = 0; j < word.length(); j++) {
                if (node.wordIndex >= 0 && node.wordIndex != i && isPalindrome(word, j, word.length() - 1)) {
                    result.add(Arrays.asList(i, node.wordIndex));
                }
                int idx = word.charAt(j) - 'a';
                if (node.children[idx] == null) { node = null; break; }
                node = node.children[idx];
            }
            if (node != null) {
                for (int idx : node.palindromeSuffixes) {
                    if (idx != i) result.add(Arrays.asList(i, idx));
                }
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(palindromePairs(new String[]{"abcd","dcba","lls","s","sssll"}));
        // [[0,1],[1,0],[2,4],[3,2]]
        System.out.println(palindromePairs(new String[]{"bat","tab","cat"}));
        // [[0,1],[1,0]]
        System.out.println(palindromePairs(new String[]{"a",""}));
        // [[0,1],[1,0]]
    }
}
