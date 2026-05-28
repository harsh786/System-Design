/**
 * Problem 50: Maximize the Confusion of an Exam (LeetCode 2024)
 * 
 * Approach: Two passes of sliding window - one flipping T->F, one flipping F->T.
 * Window invariant: at most k flips of the minority character in window.
 * Same as "Longest Repeating Character Replacement" for binary string.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like finding the longest streak you can maintain by
 * overriding at most k decisions - useful in A/B test analysis.
 */
public class Problem50_MaximizeTheConfusionOfAnExam {
    public static int maxConsecutiveAnswers(String answerKey, int k) {
        return Math.max(longest(answerKey, k, 'T'), longest(answerKey, k, 'F'));
    }

    private static int longest(String s, int k, char flip) {
        int left = 0, count = 0, max = 0;
        for (int right = 0; right < s.length(); right++) {
            if (s.charAt(right) == flip) count++;
            while (count > k) {
                if (s.charAt(left) == flip) count--;
                left++;
            }
            max = Math.max(max, right - left + 1);
        }
        return max;
    }

    public static void main(String[] args) {
        System.out.println(maxConsecutiveAnswers("TTFF", 2));    // 4
        System.out.println(maxConsecutiveAnswers("TFFT", 1));    // 3
        System.out.println(maxConsecutiveAnswers("TTFTTFTT", 1)); // 5
    }
}
