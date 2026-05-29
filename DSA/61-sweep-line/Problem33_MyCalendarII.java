import java.util.*;

public class Problem33_MyCalendarII {
    TreeMap<Integer, Integer> map = new TreeMap<>();

    public boolean book(int start, int end) {
        map.merge(start, 1, Integer::sum);
        map.merge(end, -1, Integer::sum);
        int active = 0;
        for (int v : map.values()) { active += v; if (active >= 3) { map.merge(start, -1, Integer::sum); map.merge(end, 1, Integer::sum); return false; } }
        return true;
    }

    public static void main(String[] args) {
        Problem33_MyCalendarII cal = new Problem33_MyCalendarII();
        System.out.println(cal.book(10, 20)); // true
        System.out.println(cal.book(50, 60)); // true
        System.out.println(cal.book(10, 40)); // true
        System.out.println(cal.book(5, 15));  // false
    }
}
