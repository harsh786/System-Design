import java.util.*;

/**
 * Problem 33: My Calendar III
 * 
 * API Contract:
 * - book(start, end): Book event. Return max concurrent bookings (K-booking).
 * 
 * Complexity: O(n) per booking using sweep line
 * Data Structure: TreeMap as event timeline (+1 at start, -1 at end)
 * 
 * Production Analogy: Peak concurrent users monitoring, max server load calculation,
 * bandwidth peak detection, elevator scheduling
 */
public class Problem33_MyCalendarIII {

    static class MyCalendarThree {
        private TreeMap<Integer, Integer> timeline;

        public MyCalendarThree() { timeline = new TreeMap<>(); }

        public int book(int start, int end) {
            timeline.merge(start, 1, Integer::sum);
            timeline.merge(end, -1, Integer::sum);
            int max = 0, active = 0;
            for (int val : timeline.values()) {
                active += val;
                max = Math.max(max, active);
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
