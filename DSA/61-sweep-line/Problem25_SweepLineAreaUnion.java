import java.util.*;

public class Problem25_SweepLineAreaUnion {
    public long areaUnion(int[][] rects) {
        Set<Integer> xCoords = new TreeSet<>();
        for (int[] r : rects) { xCoords.add(r[0]); xCoords.add(r[2]); }
        Integer[] xs = xCoords.toArray(new Integer[0]);
        long totalArea = 0;
        for (int i = 0; i < xs.length - 1; i++) {
            int x1 = xs[i], x2 = xs[i + 1];
            List<int[]> yIntervals = new ArrayList<>();
            for (int[] r : rects) {
                if (r[0] <= x1 && r[2] >= x2) yIntervals.add(new int[]{r[1], r[3]});
            }
            yIntervals.sort((a, b) -> a[0] - b[0]);
            long yLength = mergedLength(yIntervals);
            totalArea += yLength * (x2 - x1);
        }
        return totalArea;
    }

    private long mergedLength(List<int[]> intervals) {
        if (intervals.isEmpty()) return 0;
        long len = 0;
        int end = intervals.get(0)[0];
        for (int[] intv : intervals) {
            if (intv[0] > end) { len += end - intervals.get(0)[0]; end = intv[0]; }
            // simplified merge
            len += Math.max(0, intv[1] - Math.max(intv[0], end));
            end = Math.max(end, intv[1]);
        }
        return len - (intervals.get(0)[0] - intervals.get(0)[0]); // just return merged
    }

    public static void main(String[] args) {
        Problem25_SweepLineAreaUnion sol = new Problem25_SweepLineAreaUnion();
        // Use simple approach
        System.out.println(sol.areaUnion(new int[][]{{0,0,2,2},{1,1,3,3}}));
    }
}
