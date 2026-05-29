import java.util.*;

public class Problem26_ActiveIntervalsAtTimeT {
    public int activeAt(int[][] intervals, int t) {
        int count = 0;
        for (int[] intv : intervals) {
            if (intv[0] <= t && t < intv[1]) count++;
        }
        return count;
    }

    /* Sweep line approach for multiple queries */
    public int[] activeAtMultiple(int[][] intervals, int[] queries) {
        TreeMap<Integer, Integer> sweep = new TreeMap<>();
        for (int[] intv : intervals) { sweep.merge(intv[0], 1, Integer::sum); sweep.merge(intv[1], -1, Integer::sum); }
        TreeMap<Integer, Integer> prefix = new TreeMap<>();
        int sum = 0;
        for (Map.Entry<Integer, Integer> e : sweep.entrySet()) { sum += e.getValue(); prefix.put(e.getKey(), sum); }
        int[] res = new int[queries.length];
        for (int i = 0; i < queries.length; i++) {
            Map.Entry<Integer, Integer> entry = prefix.floorEntry(queries[i]);
            res[i] = entry == null ? 0 : entry.getValue();
        }
        return res;
    }

    public static void main(String[] args) {
        Problem26_ActiveIntervalsAtTimeT sol = new Problem26_ActiveIntervalsAtTimeT();
        System.out.println(Arrays.toString(sol.activeAtMultiple(new int[][]{{1,5},{2,6},{4,8}}, new int[]{3,5,7})));
    }
}
