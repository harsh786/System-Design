/**
 * Problem: Text Justification (LeetCode 68)
 * Approach: Greedy line packing, distribute spaces evenly with remainder
 * Complexity: O(n) time where n=total chars, O(n) space
 * Production Analogy: Document layout engine, text rendering pipeline
 */
import java.util.*;
public class Problem06_TextJustification {
    public List<String> fullJustify(String[] words, int maxWidth) {
        List<String> res = new ArrayList<>();
        int i = 0;
        while (i < words.length) {
            int j = i, len = 0;
            while (j < words.length && len + words[j].length() + (j-i) <= maxWidth)
                len += words[j++].length();
            StringBuilder line = new StringBuilder();
            int spaces = maxWidth - len;
            int gaps = j - i - 1;
            for (int k = i; k < j; k++) {
                line.append(words[k]);
                if (k < j-1) {
                    int sp = (j==words.length) ? 1 : spaces/gaps + (k-i < spaces%gaps ? 1 : 0);
                    for (int s=0; s<sp; s++) line.append(' ');
                }
            }
            while (line.length() < maxWidth) line.append(' ');
            res.add(line.toString());
            i = j;
        }
        return res;
    }
    public static void main(String[] args) {
        List<String> r = new Problem06_TextJustification().fullJustify(
            new String[]{"This","is","an","example","of","text","justification."}, 16);
        r.forEach(l -> System.out.println("|"+l+"|"));
    }
}
