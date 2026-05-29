import java.util.*;

/**
 * Problem 31: My Calendar I
 * 
 * API Contract:
 * - book(start, end): Book [start, end). Return true if no overlap.
 * 
 * Complexity: O(log n) with TreeMap
 * Data Structure: TreeMap<start, end>
 * 
 * Production Analogy: Meeting room booking, resource reservation systems,
 * appointment scheduling, cloud VM scheduling
 */
public class Problem31_MyCalendarI {

    static class MyCalendar {
        private TreeMap<Integer, Integer> calendar;

        public MyCalendar() { calendar = new TreeMap<>(); }

        public boolean book(int start, int end) {
            Integer prev = calendar.floorKey(start);
            Integer next = calendar.ceilingKey(start);
            if (prev != null && calendar.get(prev) > start) return false;
            if (next != null && next < end) return false;
            calendar.put(start, end);
            return true;
        }
    }

    public static void main(String[] args) {
        MyCalendar cal = new MyCalendar();
        assert cal.book(10, 20);
        assert !cal.book(15, 25);
        assert cal.book(20, 30);
        assert !cal.book(5, 11);
        assert cal.book(5, 10);

        System.out.println("All tests passed!");
    }
}
