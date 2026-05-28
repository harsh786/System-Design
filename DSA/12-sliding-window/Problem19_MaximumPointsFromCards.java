/**
 * Problem 19: Maximum Points You Can Obtain from Cards (LeetCode 1423)
 * 
 * Approach: Find minimum sum subarray of size (n-k). Answer = total - minWindow.
 * Window invariant: fixed window of size (n-k), track its sum.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like choosing which end-of-day batches to process first
 * to maximize value within a limited processing budget.
 */
public class Problem19_MaximumPointsFromCards {
    public static int maxScore(int[] cardPoints, int k) {
        int n = cardPoints.length;
        int total = 0;
        for (int c : cardPoints) total += c;
        if (k == n) return total;
        int windowSize = n - k;
        int windowSum = 0;
        for (int i = 0; i < windowSize; i++) windowSum += cardPoints[i];
        int minWindow = windowSum;
        for (int i = windowSize; i < n; i++) {
            windowSum += cardPoints[i] - cardPoints[i - windowSize];
            minWindow = Math.min(minWindow, windowSum);
        }
        return total - minWindow;
    }

    public static void main(String[] args) {
        System.out.println(maxScore(new int[]{1,2,3,4,5,6,1}, 3)); // 12
        System.out.println(maxScore(new int[]{2,2,2}, 2));          // 4
        System.out.println(maxScore(new int[]{9,7,7,9,7,7,9}, 7)); // 55
    }
}
