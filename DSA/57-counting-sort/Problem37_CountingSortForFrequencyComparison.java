import java.util.*;

public class Problem37_CountingSortForFrequencyComparison {
    // Compare frequency distributions of two strings
    public static boolean closeStrings(String word1, String word2) {
        if (word1.length() != word2.length()) return false;
        int[] c1 = new int[26], c2 = new int[26];
        for (char c : word1.toCharArray()) c1[c-'a']++;
        for (char c : word2.toCharArray()) c2[c-'a']++;
        for (int i = 0; i < 26; i++) if ((c1[i]==0) != (c2[i]==0)) return false;
        Arrays.sort(c1); Arrays.sort(c2);
        return Arrays.equals(c1, c2);
    }

    public static void main(String[] args) {
        System.out.println(closeStrings("abc", "bca")); // true
        System.out.println(closeStrings("aabbcc", "aabbc")); // false
    }
}
