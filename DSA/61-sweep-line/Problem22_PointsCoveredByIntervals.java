import java.util.*;

public class Problem22_PointsCoveredByIntervals {
    public int[] pointsCovered(int[][] intervals, int[] points) {
        TreeMap<Integer, Integer> sweep = new TreeMap<>();
        for (int[] intv : intervals) { sweep.merge(intv[0], 1, Integer::sum); sweep.merge(intv[1] + 1, -1, Integer::sum); }
        TreeMap<Integer, Integer> prefix = new TreeMap<>();
        int sum = 0;
        for (Map.Entry<Integer, Integer> e : sweep.entrySet()) { sum += e.getValue(); prefix.put(e.getKey(), sum); }
        int[] res = new int[points.length];
        for (int i = 0; i < points.length; i++) {
            Map.Entry<Integer, Integer> entry = prefix.floorEntry(points[i]);
            res[i] = entry == null ? 0 : entry.getValue();
        }
        return res;
    }

    public static void main(String[] args) {
        Problem22_PointsCoveredByIntervals sol = new Problem22_PointsCoveredByIntervals();
        System.out.println(Arrays.toString(sol.pointsCovered(new int[][]{{1,5},{3,7},{4,6}}, new int[]{2,4,8})));
    }
}
