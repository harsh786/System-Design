import java.util.*;

/**
 * Problem 45: Meeting Rooms III (LeetCode 2402)
 * 
 * Approach: Min-heap for available rooms (by index), min-heap for busy rooms (by end time).
 * Track meeting count per room.
 * 
 * Time Complexity: O(M log N) where M = meetings, N = rooms
 * Space Complexity: O(N)
 * 
 * Production Analogy: Server utilization tracking - finding which server handles
 * the most requests when requests queue up during high load.
 */
public class Problem45_MeetingRoomsIII {
    
    public int mostBooked(int n, int[][] meetings) {
        Arrays.sort(meetings, (a, b) -> a[0] - b[0]);
        int[] count = new int[n];
        PriorityQueue<Integer> available = new PriorityQueue<>();
        PriorityQueue<long[]> busy = new PriorityQueue<>((a, b) -> 
            a[0] != b[0] ? Long.compare(a[0], b[0]) : Long.compare(a[1], b[1]));
        
        for (int i = 0; i < n; i++) available.offer(i);
        
        for (int[] m : meetings) {
            long start = m[0], end = m[1];
            while (!busy.isEmpty() && busy.peek()[0] <= start) {
                available.offer((int) busy.poll()[1]);
            }
            if (available.isEmpty()) {
                long[] earliest = busy.poll();
                long delay = earliest[0] - start;
                end += delay;
                start = earliest[0];
                available.offer((int) earliest[1]);
            }
            int room = available.poll();
            count[room]++;
            busy.offer(new long[]{end, room});
        }
        
        int maxRoom = 0;
        for (int i = 1; i < n; i++) if (count[i] > count[maxRoom]) maxRoom = i;
        return maxRoom;
    }
    
    public static void main(String[] args) {
        Problem45_MeetingRoomsIII sol = new Problem45_MeetingRoomsIII();
        System.out.println(sol.mostBooked(2, new int[][]{{0,10},{1,5},{2,7},{3,4}})); // 0
        System.out.println(sol.mostBooked(3, new int[][]{{1,20},{2,10},{3,5},{4,9},{6,8}})); // 1
    }
}
