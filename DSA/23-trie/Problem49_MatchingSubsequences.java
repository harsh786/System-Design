import java.util.*;

/**
 * Problem 49: Number of Matching Subsequences (Trie approach)
 * 
 * Given string s and array of words, count how many words are subsequences of s.
 * Use trie-like bucketing: group waiting pointers by next character needed.
 * 
 * Time Complexity: O(s.length + sum of word lengths)
 * Space Complexity: O(number of words)
 * 
 * Production Analogy: Event stream filtering (finding patterns in event sequences),
 * DNA subsequence matching, log pattern detection, email rule matching.
 */
public class Problem49_MatchingSubsequences {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        int count = 0; // words ending here
    }

    // Bucket approach (trie-inspired): group word iterators by next needed char
    public static int numMatchingSubseq(String s, String[] words) {
        // Each bucket holds (word, index) pairs waiting for that character
        @SuppressWarnings("unchecked")
        List<int[]>[] buckets = new List[26]; // bucket[c] = list of [wordIdx, posInWord]
        for (int i = 0; i < 26; i++) buckets[i] = new ArrayList<>();

        for (int i = 0; i < words.length; i++) {
            int firstChar = words[i].charAt(0) - 'a';
            buckets[firstChar].add(new int[]{i, 0});
        }

        int count = 0;
        for (char c : s.toCharArray()) {
            List<int[]> current = buckets[c - 'a'];
            buckets[c - 'a'] = new ArrayList<>();
            for (int[] pair : current) {
                int wordIdx = pair[0], pos = pair[1];
                pos++;
                if (pos == words[wordIdx].length()) {
                    count++;
                } else {
                    int nextChar = words[wordIdx].charAt(pos) - 'a';
                    buckets[nextChar].add(new int[]{wordIdx, pos});
                }
            }
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(numMatchingSubseq("abcde", new String[]{"a","bb","acd","ace"})); // 3
        System.out.println(numMatchingSubseq("dsahjpjauf", new String[]{"ahjpjau","ja","ahbwzgqnuk","tnmlanrat"})); // 2
        System.out.println(numMatchingSubseq("a", new String[]{"a","a","a"})); // 3
    }
}
