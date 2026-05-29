/**
 * Problem: My Calendar II (LeetCode 731)
 * Approach: Two lists - bookings and overlaps; triple booking = overlap with overlap
 * Complexity: O(n) per booking
 * Production Analogy: Double-booking detection in scheduling systems
 */
import java.util.*;
public class Problem36_MyCalendarII {
    List<int[]> bookings = new ArrayList<>(), overlaps = new ArrayList<>();
    public boolean book(int start, int end) {
        for (int[] o : overlaps)
            if (start < o[1] && end > o[0]) return false;
        for (int[] b : bookings)
            if (start < b[1] && end > b[0])
                overlaps.add(new int[]{Math.max(start, b[0]), Math.min(end, b[1])});
        bookings.add(new int[]{start, end});
        return true;
    }
    public static void main(String[] args) {
        Problem36_MyCalendarII cal = new Problem36_MyCalendarII();
        System.out.println(cal.book(10, 20)); // true
        System.out.println(cal.book(50, 60)); // true
        System.out.println(cal.book(10, 40)); // true
        System.out.println(cal.book(5, 15));  // false
    }
}
