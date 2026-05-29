/**
 * Problem 35: Find the Longest Substring Containing Vowels in Even Counts
 * 
 * Approach: Use 5-bit bitmask for parity of each vowel (a,e,i,o,u). Track first occurrence.
 * Time: O(n), Space: O(32) = O(1)
 * 
 * Production Analogy: Finding longest valid session window with balanced event types.
 */
import java.util.*;

public class Problem35_LongestSubstringVowelsEvenCounts {
    public static int findTheLongestSubstring(String s) {
        Map<Integer, Integer> first = new HashMap<>();
        first.put(0, -1);
        int mask = 0, max = 0;
        String vowels = "aeiou";
        for (int i = 0; i < s.length(); i++) {
            int idx = vowels.indexOf(s.charAt(i));
            if (idx >= 0) mask ^= (1 << idx);
            first.putIfAbsent(mask, i);
            max = Math.max(max, i - first.get(mask));
        }
        return max;
    }

    public static void main(String[] args) {
        System.out.println(findTheLongestSubstring("eleetminicowoorkep")); // 13
        System.out.println(findTheLongestSubstring("leetcodeisgreat")); // 5
        System.out.println(findTheLongestSubstring("bcbcbc")); // 6
    }
}
