import java.util.*;

/**
 * Problem 32: My Calendar II
 * 
 * API Contract:
 * - book(start, end): Book event. Return false if triple booking would occur.
 *   Double booking is allowed but not triple.
 * 
 * Complexity: O(n) per booking
 * Data Structure: Two lists - single bookings + double bookings (overlaps)
 * 
 * Production Analogy: Conference room overbooking policies, airline seat reservation,
 * cloud resource overcommitment limits
 */
public class Problem32_MyCalendarII {

    static class MyCalendarTwo {
        private List<int[]> bookings;
        private List<int[]> overlaps;

        public MyCalendarTwo() {
            bookings = new ArrayList<>();
            overlaps = new ArrayList<>();
        }

        public boolean book(int start, int end) {
            // Check if overlaps with any existing double-booking
            for (int[] o : overlaps) {
                if (start < o[1] && end > o[0]) return false;
            }
            // Record overlaps with existing single bookings
            for (int[] b : bookings) {
                if (start < b[1] && end > b[0]) {
                    overlaps.add(new int[]{Math.max(start, b[0]), Math.min(end, b[1])});
                }
            }
            bookings.add(new int[]{start, end});
            return true;
        }
    }

    public static void main(String[] args) {
        MyCalendarTwo cal = new MyCalendarTwo();
        assert cal.book(10, 20);
        assert cal.book(50, 60);
        assert cal.book(10, 40); // double with [10,20)
        assert !cal.book(5, 15);  // would triple [10,15)
        assert cal.book(5, 10);  // ok, no triple
        assert cal.book(25, 55); // double with [50,60)

        System.out.println("All tests passed!");
    }
}
