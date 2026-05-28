/**
 * Problem 15: Reorganize String (LeetCode 767)
 *
 * Greedy Choice: Always place the most frequent character next, alternating positions.
 *
 * Time: O(n), Space: O(1)
 *
 * Production Analogy: Load balancing requests so same service isn't hit consecutively.
 */
import java.util.*;
public class Problem15_ReorganizeString {
    
    public static String reorganizeString(String s) {
        int[] freq = new int[26];
        for (char c : s.toCharArray()) freq[c - 'a']++;
        int maxFreq = 0, maxChar = 0;
        for (int i = 0; i < 26; i++) {
            if (freq[i] > maxFreq) { maxFreq = freq[i]; maxChar = i; }
        }
        if (maxFreq > (s.length() + 1) / 2) return "";
        char[] res = new char[s.length()];
        int idx = 0;
        // Place most frequent char at even indices
        while (freq[maxChar] > 0) { res[idx] = (char)('a' + maxChar); idx += 2; freq[maxChar]--; }
        for (int i = 0; i < 26; i++) {
            while (freq[i] > 0) {
                if (idx >= res.length) idx = 1;
                res[idx] = (char)('a' + i); idx += 2; freq[i]--;
            }
        }
        return new String(res);
    }
    
    public static void main(String[] args) {
        System.out.println(reorganizeString("aab"));  // "aba"
        System.out.println(reorganizeString("aaab")); // ""
        System.out.println(reorganizeString("vvvlo")); // "vlvov" or similar
    }
}
