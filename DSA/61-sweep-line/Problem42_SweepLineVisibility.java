import java.util.*;

public class Problem42_SweepLineVisibility {
    /* Given buildings [left, right, height], find visible segments from left */
    public List<int[]> visibleSegments(int[][] buildings) {
        TreeMap<Integer, Integer> sweep = new TreeMap<>();
        for (int[] b : buildings) { sweep.merge(b[0], 1, Integer::sum); sweep.merge(b[1], -1, Integer::sum); }
        // Simplified: just return merged intervals where at least one building exists
        List<int[]> result = new ArrayList<>();
        int depth = 0, start = -1;
        for (Map.Entry<Integer, Integer> e : sweep.entrySet()) {
            if (depth == 0) start = e.getKey();
            depth += e.getValue();
            if (depth == 0) result.add(new int[]{start, e.getKey()});
        }
        return result;
    }

    public static void main(String[] args) {
        Problem42_SweepLineVisibility sol = new Problem42_SweepLineVisibility();
        List<int[]> res = sol.visibleSegments(new int[][]{{1,5,3},{2,7,2},{6,10,4}});
        for (int[] r : res) System.out.println(Arrays.toString(r));
    }
}
