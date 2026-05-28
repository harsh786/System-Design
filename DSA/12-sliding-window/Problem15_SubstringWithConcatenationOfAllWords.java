import java.util.*;
/**
 * Problem 15: Substring with Concatenation of All Words (LeetCode 30)
 * 
 * Approach: Fixed window of size words.length * wordLen. Slide by wordLen steps.
 * Try all starting offsets [0..wordLen-1].
 * Window invariant: word frequency in window matches target frequency.
 * 
 * Time: O(n * wordLen), Space: O(words count)
 * 
 * Production Analogy: Like detecting a specific combination of fixed-size log entries
 * in a streaming buffer.
 */
public class Problem15_SubstringWithConcatenationOfAllWords {
    public static List<Integer> findSubstring(String s, String[] words) {
        List<Integer> result = new ArrayList<>();
        if (s.isEmpty() || words.length == 0) return result;
        int wordLen = words[0].length(), wordCount = words.length;
        int totalLen = wordLen * wordCount;
        Map<String, Integer> target = new HashMap<>();
        for (String w : words) target.merge(w, 1, Integer::sum);

        for (int offset = 0; offset < wordLen; offset++) {
            Map<String, Integer> window = new HashMap<>();
            int left = offset, count = 0;
            for (int right = offset; right + wordLen <= s.length(); right += wordLen) {
                String word = s.substring(right, right + wordLen);
                if (target.containsKey(word)) {
                    window.merge(word, 1, Integer::sum);
                    count++;
                    while (window.get(word) > target.get(word)) {
                        String lw = s.substring(left, left + wordLen);
                        window.merge(lw, -1, Integer::sum);
                        count--;
                        left += wordLen;
                    }
                    if (count == wordCount) result.add(left);
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
