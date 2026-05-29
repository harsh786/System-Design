import java.util.*;

/**
 * Problem 35: Meeting Rooms
 * 
 * Given intervals representing meeting times, determine if a person can attend all meetings.
 * 
 * Approach: Sort by start time, check for overlaps.
 * Time Complexity: O(n log n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Conflict detection in scheduling systems - checking if a resource
 * (conference room, deployment window) has double-bookings.
 */
public class Problem35_MeetingRooms {
    
    public boolean canAttendMeetings(int[][] intervals) {
        Arrays.sort(intervals, (a, b) -> a[0] - b[0]);
        for (int i = 1; i < intervals.length; i++) {
            if (intervals[i][0] < intervals[i-1][1]) return false;
        }
        return true;
    }
    
    public static void main(String[] args) {
        Problem35_MeetingRooms sol = new Problem35_MeetingRooms();
        
        System.out.println("Test 1: " + sol.canAttendMeetings(new int[][]{{0,30},{5,10},{15,20}})); // false
        System.out.println("Test 2: " + sol.canAttendMeetings(new int[][]{{7,10},{2,4}})); // true
        System.out.println("Test 3: " + sol.canAttendMeetings(new int[][]{{1,5},{5,10}})); // true (no overlap at boundary)
        System.out.println("Test 4: " + sol.canAttendMeetings(new int[][]{})); // true
    }
}
