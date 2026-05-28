import java.util.*;

/**
 * Problem 46: Find Common Characters
 * Find characters that appear in all strings (including duplicates).
 *
 * Approach: Track minimum frequency of each char across all strings.
 *
 * Time Complexity: O(n * k)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like finding common capabilities across all nodes in a cluster
 * for feature negotiation (minimum common denominator).
 */
public class Problem46_FindCommonCharacters {
    public List<String> commonChars(String[] words) {
        int[] minFreq = new int[26];
        Arrays.fill(minFreq, Integer.MAX_VALUE);
        for (String w : words) {
            int[] freq = new int[26];
            for (char c : w.toCharArray()) freq[c - 'a']++;
            for (int i = 0; i < 26; i++) minFreq[i] = Math.min(minFreq[i], freq[i]);
        }
        List<String> result = new ArrayList<>();
        for (int i = 0; i < 26; i++)
            for (int j = 0; j < minFreq[i]; j++)
                result.add(String.valueOf((char)('a' + i)));
        return result;
    }

    public static void main(String[] args) {
        Problem46_FindCommonCharacters sol = new Problem46_FindCommonCharacters();
        System.out.println(sol.commonChars(new String[]{"bella","label","roller"})); // [e, l, l]
        System.out.println(sol.commonChars(new String[]{"cool","lock","cook"})); // [c, o]
    }
}
