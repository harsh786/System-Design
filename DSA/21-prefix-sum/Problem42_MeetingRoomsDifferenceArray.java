/**
 * Problem 42: Meeting Rooms via Difference Array (LeetCode 253 variant)
 * 
 * Pattern: Difference array / sweep line. +1 at start, -1 at end. Peak of prefix sum = min rooms.
 * 
 * Time: O(n log n) or O(maxTime), Space: O(maxTime) or O(n)
 * 
 * Production Analogy: Computing peak concurrent database connections from
 * connection open/close timestamps for pool sizing.
 */
import java.util.*;

public class Problem42_MeetingRoomsDifferenceArray {

    public static int minMeetingRooms(int[][] intervals) {
        TreeMap<Integer, Integer> timeline = new TreeMap<>();
        for (int[] iv : intervals) {
            timeline.merge(iv[0], 1, Integer::sum);
            timeline.merge(iv[1], -1, Integer::sum);
        }
        int maxRooms = 0, curr = 0;
        for (int delta : timeline.values()) {
            curr += delta;
            maxRooms = Math.max(maxRooms, curr);
        }
        return maxRooms;
    }

    public static void main(String[] args) {
        assert minMeetingRooms(new int[][]{{0,30},{5,10},{15,20}}) == 2;
        assert minMeetingRooms(new int[][]{{7,10},{2,4}}) == 1;
        assert minMeetingRooms(new int[][]{{1,5},{2,6},{3,7},{4,8}}) == 4;
        assert minMeetingRooms(new int[][]{}) == 0;
        System.out.println("All tests passed!");
    }
}
