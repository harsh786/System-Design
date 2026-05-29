import java.util.*;

public class Problem32_MyCalendarI {
    TreeMap<Integer, Integer> calendar = new TreeMap<>();

    public boolean book(int start, int end) {
        Map.Entry<Integer, Integer> prev = calendar.floorEntry(start);
        Map.Entry<Integer, Integer> next = calendar.ceilingEntry(start);
        if ((prev != null && prev.getValue() > start) || (next != null && next.getKey() < end)) return false;
        calendar.put(start, end);
        return true;
    }

    public static void main(String[] args) {
        Problem32_MyCalendarI cal = new Problem32_MyCalendarI();
        System.out.println(cal.book(10, 20)); // true
        System.out.println(cal.book(15, 25)); // false
        System.out.println(cal.book(20, 30)); // true
    }
}
