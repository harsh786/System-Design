import java.util.*;

/**
 * Problem 27: Text Justification (LeetCode 68)
 * 
 * Approach: Greedy - pack words into lines, distribute spaces evenly. O(n) time.
 * 
 * Production Analogy: Like typesetting in a document renderer - distributing whitespace
 * evenly for justified text alignment.
 */
public class Problem27_TextJustification {

    public static List<String> fullJustify(String[] words, int maxWidth) {
        List<String> result = new ArrayList<>();
        int i = 0;
        while (i < words.length) {
            int j = i, lineLen = 0;
            while (j < words.length && lineLen + words[j].length() + (j - i) <= maxWidth) {
                lineLen += words[j].length();
                j++;
            }
            int spaces = maxWidth - lineLen;
            int gaps = j - i - 1;
            StringBuilder sb = new StringBuilder();
            if (gaps == 0 || j == words.length) { // single word or last line
                for (int k = i; k < j; k++) {
                    sb.append(words[k]);
                    if (k < j - 1) sb.append(' ');
                }
                while (sb.length() < maxWidth) sb.append(' ');
            } else {
                int spacePerGap = spaces / gaps;
                int extra = spaces % gaps;
                for (int k = i; k < j; k++) {
                    sb.append(words[k]);
                    if (k < j - 1) {
                        int sp = spacePerGap + (k - i < extra ? 1 : 0);
                        for (int x = 0; x < sp; x++) sb.append(' ');
                    }
                }
            }
            result.add(sb.toString());
            i = j;
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(fullJustify(
            new String[]{"This","is","an","example","of","text","justification."}, 16));
        System.out.println(fullJustify(
            new String[]{"What","must","be","acknowledgment","shall","be"}, 16));
    }
}
