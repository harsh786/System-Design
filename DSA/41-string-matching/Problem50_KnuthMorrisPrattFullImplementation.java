import java.util.*;

// Knuth-Morris-Pratt Full Implementation
public class Problem50_KnuthMorrisPrattFullImplementation {

    // KMP failure function utility
    static int[] computeFailure(String pattern) {
        int[] fail = new int[pattern.length()];
        int j = 0;
        for (int i = 1; i < pattern.length(); i++) {
            while (j > 0 && pattern.charAt(i) != pattern.charAt(j)) j = fail[j - 1];
            if (pattern.charAt(i) == pattern.charAt(j)) j++;
            fail[i] = j;
        }
        return fail;
    }

    static List<Integer> search(String text, String pattern) {
        List<Integer> result = new ArrayList<>();
        if (pattern.isEmpty()) return result;
        int[] fail = computeFailure(pattern);
        int j = 0;
        for (int i = 0; i < text.length(); i++) {
            while (j > 0 && text.charAt(i) != pattern.charAt(j)) j = fail[j - 1];
            if (text.charAt(i) == pattern.charAt(j)) j++;
            if (j == pattern.length()) {
                result.add(i - j + 1);
                j = fail[j - 1];
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println("Knuth-Morris-Pratt Full Implementation");
        String text = "ababcababcabc";
        String pattern = "abc";
        List<Integer> matches = search(text, pattern);
        System.out.println("Pattern found at indices: " + matches);
    }
}
