import java.util.*;

public class Problem03_MyCalendarII {
    // LC 731: Allow double booking but not triple booking
    TreeMap<Integer, Integer> map;

    public Problem03_MyCalendarII() {
        map = new TreeMap<>();
    }

    public boolean book(int start, int end) {
        map.merge(start, 1, Integer::sum);
        map.merge(end, -1, Integer::sum);
        int active = 0;
        for (int v : map.values()) {
            active += v;
            if (active >= 3) {
                map.merge(start, -1, Integer::sum);
                map.merge(end, 1, Integer::sum);
                if (map.get(start) == 0) map.remove(start);
                if (map.get(end) == 0) map.remove(end);
                return false;
            }
        }
        return true;
    }

    public static void main(String[] args) {
        Problem03_MyCalendarII cal = new Problem03_MyCalendarII();
        System.out.println(cal.book(10, 20)); // true
        System.out.println(cal.book(50, 60)); // true
        System.out.println(cal.book(10, 40)); // true
        System.out.println(cal.book(5, 15));  // false
    }
}
