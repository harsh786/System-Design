import java.util.*;

/**
 * Problem 48: Substring with Concatenation of All Words (LeetCode 30)
 * 
 * Find all starting indices where concatenation of all words (same length) appears.
 * Approach: Sliding window with word-level steps. O(n * wordLen) time.
 * 
 * Production Analogy: Like finding all positions in a byte stream where a set of
 * fixed-size protocol frames appear consecutively.
 */
public class Problem48_SubstringConcatenationAllWords {

    public static List<Integer> findSubstring(String s, String[] words) {
        List<Integer> result = new ArrayList<>();
        if (s.isEmpty() || words.length == 0) return result;
        int wordLen = words[0].length(), totalLen = wordLen * words.length;
        Map<String, Integer> wordCount = new HashMap<>();
        for (String w : words) wordCount.merge(w, 1, Integer::sum);
        
        for (int i = 0; i < wordLen; i++) {
            Map<String, Integer> window = new HashMap<>();
            int left = i, count = 0;
            for (int right = i; right + wordLen <= s.length(); right += wordLen) {
                String word = s.substring(right, right + wordLen);
                if (wordCount.containsKey(word)) {
                    window.merge(word, 1, Integer::sum);
                    count++;
                    while (window.get(word) > wordCount.get(word)) {
                        String lw = s.substring(left, left + wordLen);
                        window.merge(lw, -1, Integer::sum);
                        count--;
                        left += wordLen;
                    }
                    if (count == words.length) result.add(left);
                } else {
                    window.clear();
                    count = 0;
                    left = right + wordLen;
                }
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(findSubstring("barfoothefoobarman", new String[]{"foo","bar"})); // [0, 9]
        System.out.println(findSubstring("wordgoodgoodgoodbestword", new String[]{"word","good","best","word"})); // []
        System.out.println(findSubstring("barfoofoobarthefoobarman", new String[]{"bar","foo","the"})); // [6, 9, 12]
    }
}
