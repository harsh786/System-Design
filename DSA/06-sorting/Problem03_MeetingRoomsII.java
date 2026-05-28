import java.util.*;

/**
 * Problem 3: Meeting Rooms II
 * 
 * Given an array of meeting time intervals, find the minimum number of conference rooms required.
 * 
 * Approach: Sort start/end times separately. Use two pointers - when a meeting starts before 
 * another ends, we need an extra room.
 * Time Complexity: O(n log n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Auto-scaling compute instances based on concurrent request load.
 * Peak concurrent connections determine minimum server pool size.
 */
public class Problem03_MeetingRoomsII {
    
    public int minMeetingRooms(int[][] intervals) {
        if (intervals == null || intervals.length == 0) return 0;
        
        int n = intervals.length;
        int[] starts = new int[n];
        int[] ends = new int[n];
        
        for (int i = 0; i < n; i++) {
            starts[i] = intervals[i][0];
            ends[i] = intervals[i][1];
        }
        
        Arrays.sort(starts);
        Arrays.sort(ends);
        
        int rooms = 0, endPtr = 0;
        for (int i = 0; i < n; i++) {
            if (starts[i] < ends[endPtr]) {
                rooms++;
            } else {
                endPtr++;
            }
        }
        return rooms;
    }
    
    // Alternative: Min-heap approach
    public int minMeetingRoomsHeap(int[][] intervals) {
        if (intervals == null || intervals.length == 0) return 0;
        Arrays.sort(intervals, (a, b) -> a[0] - b[0]);
        PriorityQueue<Integer> pq = new PriorityQueue<>();
        pq.offer(intervals[0][1]);
        
        for (int i = 1; i < intervals.length; i++) {
            if (intervals[i][0] >= pq.peek()) {
                pq.poll();
            }
            pq.offer(intervals[i][1]);
        }
        return pq.size();
    }
    
    public static void main(String[] args) {
        Problem03_MeetingRoomsII sol = new Problem03_MeetingRoomsII();
        
        int[][] t1 = {{0,30},{5,10},{15,20}};
        System.out.println("Test 1: " + sol.minMeetingRooms(t1)); // 2
        
        int[][] t2 = {{7,10},{2,4}};
        System.out.println("Test 2: " + sol.minMeetingRooms(t2)); // 1
        
        int[][] t3 = {{0,5},{5,10},{10,15}};
        System.out.println("Test 3: " + sol.minMeetingRooms(t3)); // 1
        
        int[][] t4 = {{1,5},{2,6},{3,7},{4,8}};
        System.out.println("Test 4: " + sol.minMeetingRooms(t4)); // 4
        
        int[][] t5 = {};
        System.out.println("Test 5: " + sol.minMeetingRooms(t5)); // 0
    }
}
