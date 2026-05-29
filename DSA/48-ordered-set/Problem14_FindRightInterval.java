import java.util.*;

public class Problem14_FindRightInterval {
    // LC 436: For each interval, find the smallest start >= its end
    public static int[] findRightInterval(int[][] intervals) {
        TreeMap<Integer, Integer> map = new TreeMap<>();
        for (int i = 0; i < intervals.length; i++) map.put(intervals[i][0], i);
        int[] result = new int[intervals.length];
        for (int i = 0; i < intervals.length; i++) {
            Integer key = map.ceilingKey(intervals[i][1]);
            result[i] = key == null ? -1 : map.get(key);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(findRightInterval(new int[][]{{3,4},{2,3},{1,2}})));
        // [-1, 0, 1]
    }
}
