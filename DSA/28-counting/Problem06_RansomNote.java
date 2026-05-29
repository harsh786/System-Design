/**
 * Problem: Ransom Note (LeetCode 383)
 * Approach: Count available chars in magazine, check sufficiency
 * Complexity: O(m+n) time, O(1) space
 * Production Analogy: Resource availability checking before allocation
 */
public class Problem06_RansomNote {
    public boolean canConstruct(String ransomNote, String magazine) {
        int[] count = new int[26];
        for (char c : magazine.toCharArray()) count[c-'a']++;
        for (char c : ransomNote.toCharArray()) if (--count[c-'a'] < 0) return false;
        return true;
    }
    public static void main(String[] args) {
        System.out.println(new Problem06_RansomNote().canConstruct("aa", "aab")); // true
    }
}
