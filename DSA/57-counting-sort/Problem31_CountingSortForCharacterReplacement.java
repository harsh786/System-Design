import java.util.*;

public class Problem31_CountingSortForCharacterReplacement {
    // Longest repeating character replacement using frequency count
    public static int characterReplacement(String s, int k) {
        int[] count = new int[26];
        int maxFreq = 0, maxLen = 0, left = 0;
        for (int right = 0; right < s.length(); right++) {
            count[s.charAt(right) - 'A']++;
            maxFreq = Math.max(maxFreq, count[s.charAt(right) - 'A']);
            if (right - left + 1 - maxFreq > k) { count[s.charAt(left) - 'A']--; left++; }
            maxLen = Math.max(maxLen, right - left + 1);
        }
        return maxLen;
    }

    public static void main(String[] args) {
        System.out.println(characterReplacement("AABABBA", 1)); // 4
    }
}
