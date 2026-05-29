/**
 * Problem: Count Binary Substrings (LeetCode 696)
 * Approach: Track consecutive group lengths, count min(prev, cur)
 * Complexity: O(n) time, O(1) space
 * Production Analogy: Pattern detection in binary protocol streams
 */
public class Problem30_CountBinarySubstrings {
    public int countBinarySubstrings(String s) {
        int prev = 0, cur = 1, count = 0;
        for (int i = 1; i < s.length(); i++) {
            if (s.charAt(i) == s.charAt(i-1)) cur++;
            else { count += Math.min(prev, cur); prev = cur; cur = 1; }
        }
        return count + Math.min(prev, cur);
    }
    public static void main(String[] args) {
        System.out.println(new Problem30_CountBinarySubstrings().countBinarySubstrings("00110011")); // 6
    }
}
