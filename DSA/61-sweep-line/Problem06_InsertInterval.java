import java.util.*;

public class Problem06_InsertInterval {
    public int[][] insert(int[][] intervals, int[] newInterval) {
        List<int[]> res = new ArrayList<>();
        int i = 0, n = intervals.length;
        while (i < n && intervals[i][1] < newInterval[0]) res.add(intervals[i++]);
        while (i < n && intervals[i][0] <= newInterval[1]) {
            newInterval[0] = Math.min(newInterval[0], intervals[i][0]);
            newInterval[1] = Math.max(newInterval[1], intervals[i][1]);
            i++;
        }
        res.add(newInterval);
        while (i < n) res.add(intervals[i++]);
        return res.toArray(new int[0][]);
    }

    public static void main(String[] args) {
        Problem06_InsertInterval sol = new Problem06_InsertInterval();
        int[][] res = sol.insert(new int[][]{{1,3},{6,9}}, new int[]{2,5});
        for (int[] r : res) System.out.println(Arrays.toString(r));
    }
}
