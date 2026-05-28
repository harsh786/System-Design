/**
 * Problem 38: Bag of Tokens (LeetCode 948)
 *
 * Greedy Choice: Sort tokens. Spend power on cheapest tokens (gain score), 
 * spend score on most expensive tokens (gain power).
 *
 * Time: O(n log n), Space: O(1)
 *
 * Production Analogy: Trading cheap resources for points, expensive points for resources.
 */
import java.util.*;
public class Problem38_BagOfTokens {
    
    public static int bagOfTokensScore(int[] tokens, int power) {
        Arrays.sort(tokens);
        int lo = 0, hi = tokens.length - 1, score = 0, maxScore = 0;
        while (lo <= hi) {
            if (power >= tokens[lo]) {
                power -= tokens[lo++];
                score++;
                maxScore = Math.max(maxScore, score);
            } else if (score > 0) {
                power += tokens[hi--];
                score--;
            } else break;
        }
        return maxScore;
    }
    
    public static void main(String[] args) {
        System.out.println(bagOfTokensScore(new int[]{100}, 50));          // 0
        System.out.println(bagOfTokensScore(new int[]{100,200}, 150));     // 1
        System.out.println(bagOfTokensScore(new int[]{100,200,300,400}, 200)); // 2
    }
}
