/**
 * Problem 8: Word Break
 * 
 * Given a string s and a dictionary, determine if s can be segmented into dictionary words.
 * 
 * State: dp[i] = true if s[0..i-1] can be segmented
 * Recurrence: dp[i] = true if exists j < i such that dp[j] && s[j..i-1] in dict
 * 
 * Time: O(n^2 * k) where k = avg word length for substring check
 * Space: O(n)
 * 
 * Production Analogy: Like validating if a composed URL path can be broken into
 * valid registered route segments.
 */
import java.util.*;

public class Problem08_WordBreak {

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
        System.out.println("=== Word Break ===");
        System.out.println(wordBreak("leetcode", Arrays.asList("leet","code"))); // true
        System.out.println(wordBreak("applepenapple", Arrays.asList("apple","pen"))); // true
        System.out.println(wordBreak("catsandog", Arrays.asList("cats","dog","sand","and","cat"))); // false
    }
}
