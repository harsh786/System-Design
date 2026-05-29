/**
 * Problem 45: Count Distinct Substrings using Trie
 * 
 * Count the number of distinct substrings of a given string.
 * Insert all suffixes into a trie; count total nodes = distinct substrings + 1 (empty).
 * 
 * Time Complexity: O(n^2) for inserting all suffixes
 * Space Complexity: O(n^2) worst case
 * 
 * Production Analogy: Text compression analysis, DNA sequence diversity measurement,
 * plagiarism detection (counting unique text fragments), data deduplication metrics.
 */
public class Problem45_CountDistinctSubstrings {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
    }

    public static int countDistinctSubstrings(String s) {
        TrieNode root = new TrieNode();
        int count = 0; // don't count empty string

        for (int i = 0; i < s.length(); i++) {
            TrieNode node = root;
            for (int j = i; j < s.length(); j++) {
                int idx = s.charAt(j) - 'a';
                if (node.children[idx] == null) {
                    node.children[idx] = new TrieNode();
                    count++; // new distinct substring found
                }
                node = node.children[idx];
            }
        }
        return count; // +1 if counting empty string
    }

    public static void main(String[] args) {
        System.out.println(countDistinctSubstrings("abc"));   // 6: a,b,c,ab,bc,abc
        System.out.println(countDistinctSubstrings("aab"));   // 5: a,b,aa,ab,aab
        System.out.println(countDistinctSubstrings("abab"));  // 7: a,b,ab,ba,aba,bab,abab
        System.out.println(countDistinctSubstrings("a"));     // 1
        System.out.println(countDistinctSubstrings("aaaa"));  // 4: a,aa,aaa,aaaa
    }
}
