/**
 * Problem: Minimum Number of Steps to Make Two Strings Anagram (LeetCode 1347)
 * Approach: Count char difference between strings
 * Complexity: O(n) time, O(1) space
 * Production Analogy: Computing minimum edits for data synchronization
 */
public class Problem48_MinStepsTwoStringsAnagram {
    public int minSteps(String s, String t) {
        int[] count = new int[26];
        for (int i = 0; i < s.length(); i++) { count[s.charAt(i)-'a']++; count[t.charAt(i)-'a']--; }
        int steps = 0;
        for (int c : count) if (c > 0) steps += c;
        return steps;
    }
    public static void main(String[] args) {
        System.out.println(new Problem48_MinStepsTwoStringsAnagram().minSteps("bab", "aba")); // 1
    }
}
