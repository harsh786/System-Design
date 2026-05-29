/**
 * Problem: My Calendar III (LeetCode 732)
 * Approach: Sweep line with TreeMap of events
 * Complexity: O(n) per booking
 * Production Analogy: Peak concurrent connection tracking in load balancers
 */
import java.util.*;
public class Problem37_MyCalendarIII {
    TreeMap<Integer, Integer> map = new TreeMap<>();
    public int book(int start, int end) {
        map.merge(start, 1, Integer::sum);
        map.merge(end, -1, Integer::sum);
        int max = 0, active = 0;
        for (int v : map.values()) { active += v; max = Math.max(max, active); }
        return max;
    }
    public static void main(String[] args) {
        Problem37_MyCalendarIII cal = new Problem37_MyCalendarIII();
        System.out.println(cal.book(10, 20)); // 1
        System.out.println(cal.book(50, 60)); // 1
        System.out.println(cal.book(10, 40)); // 2
        System.out.println(cal.book(5, 15));  // 3
    }
}
