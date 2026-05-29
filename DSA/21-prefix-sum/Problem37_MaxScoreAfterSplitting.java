/**
 * Problem 37: Maximum Score After Splitting a String (LeetCode 1422)
 * 
 * Pattern: Prefix count of zeros (left) + suffix count of ones (right)
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Optimal split point for binary classification threshold.
 */
public class Problem37_MaxScoreAfterSplitting {

    public static int maxScore(String s) {
        int ones = 0;
        for (char c : s.toCharArray()) if (c == '1') ones++;

        int maxScore = 0, zeros = 0;
        for (int i = 0; i < s.length() - 1; i++) {
            if (s.charAt(i) == '0') zeros++;
            else ones--;
            maxScore = Math.max(maxScore, zeros + ones);
        }
        return maxScore;
    }

    public static void main(String[] args) {
        assert maxScore("011101") == 5;
        assert maxScore("00111") == 5;
        assert maxScore("1111") == 3;
        assert maxScore("00") == 1;
        System.out.println("All tests passed!");
    }
}
