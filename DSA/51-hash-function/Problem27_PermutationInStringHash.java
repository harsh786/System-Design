import java.util.*;

public class Problem27_PermutationInStringHash {
    public boolean checkInclusion(String s1, String s2) {
        if (s1.length() > s2.length()) return false;
        int[] count = new int[26];
        for (char c : s1.toCharArray()) count[c - 'a']++;
        int[] window = new int[26];
        for (int i = 0; i < s2.length(); i++) {
            window[s2.charAt(i) - 'a']++;
            if (i >= s1.length()) window[s2.charAt(i - s1.length()) - 'a']--;
            if (Arrays.equals(count, window)) return true;
        }
        return false;
    }

    public static void main(String[] args) {
        Problem27_PermutationInStringHash sol = new Problem27_PermutationInStringHash();
        System.out.println(sol.checkInclusion("ab", "eidbaooo")); // true
    }
}
