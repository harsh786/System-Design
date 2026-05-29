/**
 * Problem 9: Corporate Flight Bookings (LeetCode 1109)
 * 
 * Pattern: Difference Array - mark +seats at start, -seats after end, then prefix sum
 * 
 * For booking [first, last, seats]: diff[first-1] += seats, diff[last] -= seats
 * Final answer is prefix sum of diff array.
 * 
 * Time: O(n + bookings), Space: O(n)
 * 
 * Production Analogy: Computing concurrent users per time slot from session
 * start/end events—exactly how APM tools calculate concurrency metrics.
 */
import java.util.Arrays;

public class Problem09_CorporateFlightBookings {

    public static int[] corpFlightBookings(int[][] bookings, int n) {
        int[] diff = new int[n + 1];
        for (int[] b : bookings) {
            diff[b[0] - 1] += b[2];
            if (b[1] < n) diff[b[1]] -= b[2];
        }
        int[] result = new int[n];
        result[0] = diff[0];
        for (int i = 1; i < n; i++)
            result[i] = result[i - 1] + diff[i];
        return result;
    }

    public static void main(String[] args) {
        assert Arrays.equals(
            corpFlightBookings(new int[][]{{1,2,10},{2,3,20},{2,5,25}}, 5),
            new int[]{10, 55, 45, 25, 25});
        assert Arrays.equals(
            corpFlightBookings(new int[][]{{1,2,10},{2,2,15}}, 2),
            new int[]{10, 25});
        System.out.println("All tests passed!");
    }
}
