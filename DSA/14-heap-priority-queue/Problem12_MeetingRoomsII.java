import java.util.*;

/**
 * Problem 12: Meeting Rooms II (LeetCode 253)
 * 
 * Approach: Sort by start time, use min-heap tracking end times of ongoing meetings.
 * If earliest ending meeting ends before new one starts, reuse that room.
 * 
 * Time Complexity: O(N log N)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Resource pool sizing - determining minimum number of database
 * connections needed to handle all concurrent queries.
 */
public class Problem12_MeetingRoomsII {
    
    public int minMeetingRooms(int[][] intervals) {
        Arrays.sort(intervals, (a, b) -> a[0] - b[0]);
        PriorityQueue<Integer> minHeap = new PriorityQueue<>(); // end times
        
        for (int[] interval : intervals) {
            if (!minHeap.isEmpty() && minHeap.peek() <= interval[0]) {
                minHeap.poll();
            }
            minHeap.offer(interval[1]);
        }
        return minHeap.size();
    }
    
    public static void main(String[] args) {
        Problem12_MeetingRoomsII sol = new Problem12_MeetingRoomsII();
        System.out.println(sol.minMeetingRooms(new int[][]{{0,30},{5,10},{15,20}})); // 2
        System.out.println(sol.minMeetingRooms(new int[][]{{7,10},{2,4}})); // 1
        System.out.println(sol.minMeetingRooms(new int[][]{{1,5},{2,6},{3,7},{4,8}})); // 4
    }
}
