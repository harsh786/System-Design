import java.util.*;

/**
 * Problem 30: Generalized Abbreviation (LeetCode 320)
 * 
 * Generate all abbreviations of a word where consecutive chars can be replaced by count.
 * e.g., "word" -> "word", "1ord", "w1rd", "wo1d", "wor1", "2rd", "w2d", ..., "4"
 * 
 * Search Tree:
 * - At each character: keep it OR abbreviate (increment count)
 * - When keeping a char, flush any accumulated count first
 * 
 * Pruning Strategy:
 * - No pruning needed; all combinations are valid
 * 
 * Time Complexity: O(2^n * n)
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Generating all possible compression schemes for identifiers in compact protocols.
 */
public class Problem30_GeneralizedAbbreviation {

    public List<String> generateAbbreviations(String word) {
        List<String> result = new ArrayList<>();
        backtrack(word, 0, 0, new StringBuilder(), result);
        return result;
    }

    private void backtrack(String word, int pos, int count, StringBuilder sb, List<String> result) {
        int len = sb.length();
        if (pos == word.length()) {
            if (count > 0) sb.append(count);
            result.add(sb.toString());
            sb.setLength(len);
            return;
        }
        // Option 1: abbreviate current char (increment count)
        backtrack(word, pos + 1, count + 1, sb, result);
        // Option 2: keep current char (flush count first)
        if (count > 0) sb.append(count);
        sb.append(word.charAt(pos));
        backtrack(word, pos + 1, 0, sb, result);
        sb.setLength(len);
    }

    public static void main(String[] args) {
        Problem30_GeneralizedAbbreviation sol = new Problem30_GeneralizedAbbreviation();

        System.out.println(sol.generateAbbreviations("word"));
        // 2^4 = 16 abbreviations
        System.out.println(sol.generateAbbreviations("a"));
        // [1, a]
    }
}
