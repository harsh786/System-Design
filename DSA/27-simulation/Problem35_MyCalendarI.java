/**
 * Problem: My Calendar I (LeetCode 729)
 * Approach: TreeMap to find overlapping intervals
 * Complexity: O(log n) per booking
 * Production Analogy: Calendar/resource reservation system with conflict detection
 */
import java.util.*;
public class Problem35_MyCalendarI {
    TreeMap<Integer, Integer> calendar = new TreeMap<>();
    public boolean book(int start, int end) {
        Map.Entry<Integer, Integer> prev = calendar.floorEntry(start);
        Map.Entry<Integer, Integer> next = calendar.ceilingEntry(start);
        if (prev != null && prev.getValue() > start) return false;
        if (next != null && next.getKey() < end) return false;
        calendar.put(start, end);
        return true;
    }
    public static void main(String[] args) {
        Problem35_MyCalendarI cal = new Problem35_MyCalendarI();
        System.out.println(cal.book(10, 20)); // true
        System.out.println(cal.book(15, 25)); // false
        System.out.println(cal.book(20, 30)); // true
    }
}
