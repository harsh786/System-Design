/**
 * Problem 43: My Calendar III (LeetCode 732) - Difference Map
 * 
 * Pattern: TreeMap as difference array. Add +1 at start, -1 at end.
 * Max prefix sum over timeline = max concurrent bookings (k-booking).
 * 
 * Time: O(n^2) worst case due to traversal per book, Space: O(n)
 * 
 * Production Analogy: Real-time peak concurrency tracking in a reservation system
 * (hotel rooms, cloud VMs, etc.)
 */
import java.util.*;

public class Problem43_MyCalendarIII {

    static class MyCalendarThree {
        TreeMap<Integer, Integer> timeline = new TreeMap<>();

        public int book(int start, int end) {
            timeline.merge(start, 1, Integer::sum);
            timeline.merge(end, -1, Integer::sum);
            int max = 0, curr = 0;
            for (int val : timeline.values()) {
                curr += val;
                max = Math.max(max, curr);
            }
            return max;
        }
    }

    public static void main(String[] args) {
        MyCalendarThree cal = new MyCalendarThree();
        assert cal.book(10, 20) == 1;
        assert cal.book(50, 60) == 1;
        assert cal.book(10, 40) == 2;
        assert cal.book(5, 15) == 3;
        assert cal.book(5, 10) == 3;
        assert cal.book(25, 55) == 3;
        System.out.println("All tests passed!");
    }
}
