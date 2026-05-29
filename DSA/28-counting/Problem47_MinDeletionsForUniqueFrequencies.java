/**
 * Problem: Minimum Deletions to Make Character Frequencies Unique (LeetCode 1647)
 * Approach: Sort frequencies descending, greedily reduce duplicates
 * Complexity: O(n + 26 log 26) time, O(1) space
 * Production Analogy: Conflict resolution in unique resource allocation
 */
import java.util.*;
public class Problem47_MinDeletionsForUniqueFrequencies {
    public int minDeletions(String s) {
        int[] freq = new int[26];
        for (char c : s.toCharArray()) freq[c-'a']++;
        Arrays.sort(freq);
        int deletions = 0;
        for (int i = 24; i >= 0; i--) {
            if (freq[i] == 0) break;
            if (freq[i] >= freq[i+1]) {
                int target = Math.max(0, freq[i+1]-1);
                deletions += freq[i] - target;
                freq[i] = target;
            }
        }
        return deletions;
    }
    public static void main(String[] args) {
        System.out.println(new Problem47_MinDeletionsForUniqueFrequencies().minDeletions("aaabbbcc")); // 2
    }
}
