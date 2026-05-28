import java.util.*;

/**
 * Problem 32: Seat Reservation Manager (LeetCode 1845)
 * 
 * Approach: Min-heap to always give the smallest available seat number.
 * 
 * Time Complexity: O(log N) per operation
 * Space Complexity: O(N)
 * 
 * Production Analogy: Connection pool management - allocating the lowest-numbered
 * available connection slot, recycling returned connections.
 */
public class Problem32_SeatReservationManager {
    
    private PriorityQueue<Integer> available;
    
    public Problem32_SeatReservationManager(int n) {
        available = new PriorityQueue<>();
        for (int i = 1; i <= n; i++) available.offer(i);
    }
    
    public int reserve() { return available.poll(); }
    public void unreserve(int seatNumber) { available.offer(seatNumber); }
    
    public static void main(String[] args) {
        Problem32_SeatReservationManager mgr = new Problem32_SeatReservationManager(5);
        System.out.println(mgr.reserve());   // 1
        System.out.println(mgr.reserve());   // 2
        mgr.unreserve(2);
        System.out.println(mgr.reserve());   // 2
        System.out.println(mgr.reserve());   // 3
        System.out.println(mgr.reserve());   // 4
        mgr.unreserve(1);
        System.out.println(mgr.reserve());   // 1
    }
}
