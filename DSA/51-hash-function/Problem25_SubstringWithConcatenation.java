import java.util.*;

public class Problem25_SubstringWithConcatenation {
    public List<Integer> findSubstring(String s, String[] words) {
        List<Integer> result = new ArrayList<>();
        if (words.length == 0) return result;
        int wordLen = words[0].length(), totalLen = wordLen * words.length;
        Map<String, Integer> wordCount = new HashMap<>();
        for (String w : words) wordCount.merge(w, 1, Integer::sum);
        for (int i = 0; i <= s.length() - totalLen; i++) {
            Map<String, Integer> seen = new HashMap<>();
            boolean valid = true;
            for (int j = 0; j < words.length; j++) {
                String word = s.substring(i + j * wordLen, i + (j+1) * wordLen);
                if (!wordCount.containsKey(word)) { valid = false; break; }
                seen.merge(word, 1, Integer::sum);
                if (seen.get(word) > wordCount.get(word)) { valid = false; break; }
            }
            if (valid) result.add(i);
        }
        return result;
    }

    public static void main(String[] args) {
        Problem25_SubstringWithConcatenation sol = new Problem25_SubstringWithConcatenation();
        System.out.println(sol.findSubstring("barfoothefoobarman", new String[]{"foo","bar"})); // [0,9]
    }
}
