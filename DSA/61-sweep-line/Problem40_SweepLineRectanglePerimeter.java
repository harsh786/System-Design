import java.util.*;

public class Problem40_SweepLineRectanglePerimeter {
    public long rectangleUnionPerimeter(int[][] rects) {
        // Horizontal contribution
        long perimeter = 0;
        perimeter += sweepContribution(rects, true);
        perimeter += sweepContribution(rects, false);
        return perimeter;
    }

    private long sweepContribution(int[][] rects, boolean horizontal) {
        List<int[]> events = new ArrayList<>();
        for (int[] r : rects) {
            if (horizontal) { events.add(new int[]{r[0], 1, r[1], r[3]}); events.add(new int[]{r[2], -1, r[1], r[3]}); }
            else { events.add(new int[]{r[1], 1, r[0], r[2]}); events.add(new int[]{r[3], -1, r[0], r[2]}); }
        }
        events.sort((a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
        long contrib = 0, prevLen = 0;
        TreeMap<Integer, Integer> active = new TreeMap<>();
        for (int[] e : events) {
            if (e[1] == 1) { active.merge(e[2], 1, Integer::sum); active.merge(e[3], -1, Integer::sum); }
            else { active.merge(e[2], -1, Integer::sum); active.merge(e[3], 1, Integer::sum); if (active.get(e[2]) == 0) active.remove(e[2]); if (active.containsKey(e[3]) && active.get(e[3]) == 0) active.remove(e[3]); }
            long curLen = computeCoveredLength(active);
            contrib += Math.abs(curLen - prevLen);
            prevLen = curLen;
        }
        return contrib;
    }

    private long computeCoveredLength(TreeMap<Integer, Integer> active) {
        long len = 0; int depth = 0, start = 0;
        for (Map.Entry<Integer, Integer> e : active.entrySet()) {
            if (depth == 0) start = e.getKey();
            depth += e.getValue();
            if (depth == 0) len += e.getKey() - start;
        }
        return len;
    }

    public static void main(String[] args) {
        Problem40_SweepLineRectanglePerimeter sol = new Problem40_SweepLineRectanglePerimeter();
        System.out.println(sol.rectangleUnionPerimeter(new int[][]{{0,0,2,2},{1,1,3,3}}));
    }
}
