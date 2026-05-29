import java.util.*;

public class Problem04_MyCalendarIII {
    TreeMap<Integer, Integer> map = new TreeMap<>();

    public int book(int start, int end) {
        map.merge(start, 1, Integer::sum);
        map.merge(end, -1, Integer::sum);
        int active = 0, max = 0;
        for (int v : map.values()) { active += v; max = Math.max(max, active); }
        return max;
    }

    public static void main(String[] args) {
        Problem04_MyCalendarIII cal = new Problem04_MyCalendarIII();
        System.out.println(cal.book(10, 20)); // 1
        System.out.println(cal.book(50, 60)); // 1
        System.out.println(cal.book(10, 40)); // 2
        System.out.println(cal.book(5, 15));  // 3
    }
}
