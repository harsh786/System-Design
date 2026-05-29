import java.util.*;

public class Problem45_MyCalendarIWithTreeMap {
    TreeMap<Integer, Integer> calendar = new TreeMap<>();

    public boolean book(int start, int end) {
        Integer prev = calendar.floorKey(start);
        if (prev != null && calendar.get(prev) > start) return false;
        Integer next = calendar.ceilingKey(start);
        if (next != null && next < end) return false;
        calendar.put(start, end);
        return true;
    }

    public static void main(String[] args) {
        Problem45_MyCalendarIWithTreeMap cal = new Problem45_MyCalendarIWithTreeMap();
        System.out.println(cal.book(10, 20)); // true
        System.out.println(cal.book(15, 25)); // false
        System.out.println(cal.book(20, 30)); // true
    }
}
