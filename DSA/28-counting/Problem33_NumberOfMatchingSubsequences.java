/**
 * Problem: Number of Matching Subsequences (LeetCode 792)
 * Approach: Bucket words by next char needed, iterate through s
 * Complexity: O(s + sum of word lengths) time
 * Production Analogy: Event-driven pattern matching in log processing
 */
import java.util.*;
public class Problem33_NumberOfMatchingSubsequences {
    public int numMatchingSubseq(String s, String[] words) {
        List<int[]>[] buckets = new List[26]; // int[] = {wordIdx, charIdx}
        for (int i = 0; i < 26; i++) buckets[i] = new ArrayList<>();
        for (int i = 0; i < words.length; i++) buckets[words[i].charAt(0)-'a'].add(new int[]{i, 0});
        int count = 0;
        for (char c : s.toCharArray()) {
            List<int[]> current = buckets[c-'a'];
            buckets[c-'a'] = new ArrayList<>();
            for (int[] pair : current) {
                pair[1]++;
                if (pair[1] == words[pair[0]].length()) count++;
                else buckets[words[pair[0]].charAt(pair[1])-'a'].add(pair);
            }
        }
        return count;
    }
    public static void main(String[] args) {
        System.out.println(new Problem33_NumberOfMatchingSubsequences()
            .numMatchingSubseq("abcde", new String[]{"a","bb","acd","ace"})); // 3
    }
}
