import java.util.*;

public class Problem18_CountingSortForLowercaseStrings {
    public static String sortLowercase(String s) {
        int[] count = new int[26];
        for (char c : s.toCharArray()) count[c - 'a']++;
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 26; i++) while (count[i]-- > 0) sb.append((char)('a'+i));
        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(sortLowercase("zyxwvutsrqponmlkjihgfedcba"));
        System.out.println(sortLowercase("banana"));
    }
}
