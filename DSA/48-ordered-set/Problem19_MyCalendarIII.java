import java.util.*;

public class Problem19_MyCalendarIII {
    // LC 732: Return max k-booking after each booking
    TreeMap<Integer, Integer> map;

    public Problem19_MyCalendarIII() {
        map = new TreeMap<>();
    }

    public int book(int start, int end) {
        map.merge(start, 1, Integer::sum);
        map.merge(end, -1, Integer::sum);
        int max = 0, active = 0;
        for (int v : map.values()) {
            active += v;
            max = Math.max(max, active);
        }
        return max;
    }

    public static void main(String[] args) {
        Problem19_MyCalendarIII cal = new Problem19_MyCalendarIII();
        System.out.println(cal.book(10, 20)); // 1
        System.out.println(cal.book(50, 60)); // 1
        System.out.println(cal.book(10, 40)); // 2
        System.out.println(cal.book(5, 15));  // 3
    }
}
