/**
 * Problem: Find Common Characters (LeetCode 1002)
 * Approach: Track minimum frequency across all words
 * Complexity: O(n * k) time, O(1) space
 * Production Analogy: Finding common features across multiple datasets
 */
import java.util.*;
public class Problem25_FindCommonCharacters {
    public List<String> commonChars(String[] words) {
        int[] minFreq = new int[26];
        Arrays.fill(minFreq, Integer.MAX_VALUE);
        for (String w : words) {
            int[] freq = new int[26];
            for (char c : w.toCharArray()) freq[c-'a']++;
            for (int i = 0; i < 26; i++) minFreq[i] = Math.min(minFreq[i], freq[i]);
        }
        List<String> res = new ArrayList<>();
        for (int i = 0; i < 26; i++)
            for (int j = 0; j < minFreq[i]; j++) res.add(String.valueOf((char)('a'+i)));
        return res;
    }
    public static void main(String[] args) {
        System.out.println(new Problem25_FindCommonCharacters().commonChars(
            new String[]{"bella","label","roller"})); // [e,l,l]
    }
}
