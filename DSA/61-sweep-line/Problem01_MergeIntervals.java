import java.util.*;

public class Problem01_MergeIntervals {
    public int[][] merge(int[][] intervals) {
        Arrays.sort(intervals, (a, b) -> a[0] - b[0]);
        List<int[]> res = new ArrayList<>();
        for (int[] intv : intervals) {
            if (res.isEmpty() || res.get(res.size() - 1)[1] < intv[0]) res.add(intv);
            else res.get(res.size() - 1)[1] = Math.max(res.get(res.size() - 1)[1], intv[1]);
        }
        return res.toArray(new int[0][]);
    }

    public static void main(String[] args) {
        Problem01_MergeIntervals sol = new Problem01_MergeIntervals();
        int[][] res = sol.merge(new int[][]{{1,3},{2,6},{8,10},{15,18}});
        for (int[] r : res) System.out.println(Arrays.toString(r));
    }
}
