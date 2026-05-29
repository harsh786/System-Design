import java.util.*;

public class Problem26_SeatReservationManager {
    // LC 1845: Reserve smallest available seat, unreserve seats
    TreeSet<Integer> available;

    public Problem26_SeatReservationManager(int n) {
        available = new TreeSet<>();
        for (int i = 1; i <= n; i++) available.add(i);
    }

    public int reserve() { return available.pollFirst(); }
    public void unreserve(int seatNumber) { available.add(seatNumber); }

    public static void main(String[] args) {
        Problem26_SeatReservationManager mgr = new Problem26_SeatReservationManager(5);
        System.out.println(mgr.reserve()); // 1
        System.out.println(mgr.reserve()); // 2
        mgr.unreserve(2);
        System.out.println(mgr.reserve()); // 2
    }
}
