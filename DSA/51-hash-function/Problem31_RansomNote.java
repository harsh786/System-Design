import java.util.*;

public class Problem31_RansomNote {
    public boolean canConstruct(String ransomNote, String magazine) {
        int[] count = new int[26];
        for (char c : magazine.toCharArray()) count[c - 'a']++;
        for (char c : ransomNote.toCharArray()) if (--count[c - 'a'] < 0) return false;
        return true;
    }

    public static void main(String[] args) {
        Problem31_RansomNote sol = new Problem31_RansomNote();
        System.out.println(sol.canConstruct("aa", "aab")); // true
        System.out.println(sol.canConstruct("aa", "ab")); // false
    }
}
