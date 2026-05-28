import java.util.*;

/**
 * Problem 25: Word Break (LeetCode 139)
 * 
 * Approach: DP. dp[i] = true if s[0..i) can be segmented. O(n^2 * k) time, O(n) space.
 * 
 * Production Analogy: Like URL path matching against a set of known routes -
 * checking if a path can be decomposed into valid route segments.
 */
public class Problem25_WordBreak {

    public static boolean wordBreak(String s, List<String> wordDict) {
        Set<String> dict = new HashSet<>(wordDict);
        boolean[] dp = new boolean[s.length() + 1];
        dp[0] = true;
        for (int i = 1; i <= s.length(); i++) {
            for (int j = 0; j < i; j++) {
                if (dp[j] && dict.contains(s.substring(j, i))) {
                    dp[i] = true;
                    break;
                }
            }
        }
        return dp[s.length()];
    }

    public static void main(String[] args) {
        System.out.println(wordBreak("leetcode", Arrays.asList("leet", "code"))); // true
        System.out.println(wordBreak("applepenapple", Arrays.asList("apple", "pen"))); // true
        System.out.println(wordBreak("catsandog", Arrays.asList("cats","dog","sand","and","cat"))); // false
    }
}
