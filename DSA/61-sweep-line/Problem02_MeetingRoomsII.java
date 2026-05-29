import java.util.*;

public class Problem02_MeetingRoomsII {
    public int minMeetingRooms(int[][] intervals) {
        int[] starts = new int[intervals.length], ends = new int[intervals.length];
        for (int i = 0; i < intervals.length; i++) { starts[i] = intervals[i][0]; ends[i] = intervals[i][1]; }
        Arrays.sort(starts); Arrays.sort(ends);
        int rooms = 0, endPtr = 0;
        for (int i = 0; i < starts.length; i++) {
            if (starts[i] < ends[endPtr]) rooms++;
            else endPtr++;
        }
        return rooms;
    }

    public static void main(String[] args) {
        Problem02_MeetingRoomsII sol = new Problem02_MeetingRoomsII();
        System.out.println(sol.minMeetingRooms(new int[][]{{0,30},{5,10},{15,20}})); // 2
    }
}
