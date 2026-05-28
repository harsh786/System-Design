/**
 * Problem 28: Minimum Deletions to Make Character Frequencies Unique (LeetCode 1647)
 *
 * Greedy Choice: Sort frequencies descending. If duplicate, decrement until unique or zero.
 *
 * Time: O(n), Space: O(1)
 *
 * Production Analogy: Deduplicating rate limits so no two services share same quota.
 */
import java.util.*;
public class Problem28_MinDeletionsUniqueFrequencies {
    
    public static int minDeletions(String s) {
        int[] freq = new int[26];
        for (char c : s.toCharArray()) freq[c - 'a']++;
        Arrays.sort(freq);
        int deletions = 0;
        for (int i = 23; i >= 0; i--) {
            if (freq[i] == 0) break;
            if (freq[i] >= freq[i+1]) {
                int prev = freq[i];
                freq[i] = Math.max(0, freq[i+1] - 1);
                deletions += prev - freq[i];
            }
        }
        return deletions;
    }
    
    public static void main(String[] args) {
        System.out.println(minDeletions("aab"));      // 0
        System.out.println(minDeletions("aaabbbcc")); // 2
        System.out.println(minDeletions("ceabaacb")); // 2
    }
}
