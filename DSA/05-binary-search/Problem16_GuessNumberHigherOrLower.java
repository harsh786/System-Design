/**
 * Problem 16: Guess Number Higher or Lower
 * 
 * Guess a number between 1 and n. API tells higher/lower/correct.
 * 
 * Approach: Standard binary search on [1, n].
 * 
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Binary search-based A/B testing to find optimal
 * configuration parameter (e.g., cache TTL) via feedback loop.
 */
public class Problem16_GuessNumberHigherOrLower {
    private static int pick;

    // Simulates the API: -1 = too high, 1 = too low, 0 = correct
    private static int guess(int num) {
        return Integer.compare(pick, num);
    }

    public static int guessNumber(int n) {
        int lo = 1, hi = n;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            int res = guess(mid);
            if (res == 0) return mid;
            else if (res < 0) hi = mid - 1;
            else lo = mid + 1;
        }
        return -1;
    }

    public static void main(String[] args) {
        pick = 6;
        System.out.println(guessNumber(10)); // 6
        pick = 1;
        System.out.println(guessNumber(1));  // 1
        pick = 2;
        System.out.println(guessNumber(2));  // 2
        pick = 1000000000;
        System.out.println(guessNumber(2000000000)); // 1000000000
    }
}
