import java.util.*;

public class Problem02_MyCalendarI {
    // LC 729: Implement calendar that doesn't allow double booking
    TreeMap<Integer, Integer> calendar;

    public Problem02_MyCalendarI() {
        calendar = new TreeMap<>();
    }

    public boolean book(int start, int end) {
        Integer prev = calendar.floorKey(start);
        if (prev != null && calendar.get(prev) > start) return false;
        Integer next = calendar.ceilingKey(start);
        if (next != null && next < end) return false;
        calendar.put(start, end);
        return true;
    }

    public static void main(String[] args) {
        Problem02_MyCalendarI cal = new Problem02_MyCalendarI();
        System.out.println(cal.book(10, 20)); // true
        System.out.println(cal.book(15, 25)); // false
        System.out.println(cal.book(20, 30)); // true
    }
}
