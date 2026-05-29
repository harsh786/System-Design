import java.util.*;

public class Problem18_MinimumMeetingRooms {
    public int minRooms(int[][] meetings) {
        TreeMap<Integer, Integer> sweep = new TreeMap<>();
        for (int[] m : meetings) { sweep.merge(m[0], 1, Integer::sum); sweep.merge(m[1], -1, Integer::sum); }
        int max = 0, cur = 0;
        for (int v : sweep.values()) { cur += v; max = Math.max(max, cur); }
        return max;
    }

    public static void main(String[] args) {
        Problem18_MinimumMeetingRooms sol = new Problem18_MinimumMeetingRooms();
        System.out.println(sol.minRooms(new int[][]{{0,30},{5,10},{15,20}})); // 2
    }
}
