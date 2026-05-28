/**
 * Problem 20: Meeting Rooms II (LeetCode 253)
 *
 * Greedy Choice: Sort by start time, use min-heap to track earliest ending meeting.
 * Reuse room if current meeting starts after earliest end.
 *
 * Time: O(n log n), Space: O(n)
 *
 * Production Analogy: Minimum number of server instances needed for overlapping requests.
 */
import java.util.*;
public class Problem20_MeetingRoomsII {
    
    public static int minMeetingRooms(int[][] intervals) {
        Arrays.sort(intervals, (a, b) -> a[0] - b[0]);
        PriorityQueue<Integer> pq = new PriorityQueue<>();
        for (int[] interval : intervals) {
            if (!pq.isEmpty() && pq.peek() <= interval[0]) pq.poll();
            pq.offer(interval[1]);
        }
        return pq.size();
    }
    
    public static void main(String[] args) {
        System.out.println(minMeetingRooms(new int[][]{{0,30},{5,10},{15,20}})); // 2
        System.out.println(minMeetingRooms(new int[][]{{7,10},{2,4}}));          // 1
        System.out.println(minMeetingRooms(new int[][]{{1,5},{2,6},{3,7},{4,8}})); // 4
    }
}
