import java.util.*;

public class Problem47_TimeSlotBooking {
    TreeMap<Integer, Integer> bookings = new TreeMap<>();
    int maxAllowed;

    public Problem47_TimeSlotBooking(int maxAllowed) { this.maxAllowed = maxAllowed; }

    public boolean book(int start, int end) {
        bookings.merge(start, 1, Integer::sum);
        bookings.merge(end, -1, Integer::sum);
        int cur = 0;
        for (int v : bookings.values()) { cur += v; if (cur > maxAllowed) { bookings.merge(start, -1, Integer::sum); bookings.merge(end, 1, Integer::sum); return false; } }
        return true;
    }

    public static void main(String[] args) {
        Problem47_TimeSlotBooking sol = new Problem47_TimeSlotBooking(2);
        System.out.println(sol.book(10, 20)); // true
        System.out.println(sol.book(15, 25)); // true
        System.out.println(sol.book(12, 18)); // false
    }
}
