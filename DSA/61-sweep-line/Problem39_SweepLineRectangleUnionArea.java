import java.util.*;

public class Problem39_SweepLineRectangleUnionArea {
    public long rectangleUnionArea(int[][] rects) {
        List<int[]> events = new ArrayList<>();
        Set<Integer> ySet = new TreeSet<>();
        for (int[] r : rects) { events.add(new int[]{r[0], 0, r[1], r[3]}); events.add(new int[]{r[2], 1, r[1], r[3]}); ySet.add(r[1]); ySet.add(r[3]); }
        events.sort((a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
        Integer[] ys = ySet.toArray(new Integer[0]);
        int[] count = new int[ys.length - 1];
        long area = 0;
        int prevX = events.get(0)[0];
        for (int[] e : events) {
            long coveredY = 0;
            for (int i = 0; i < count.length; i++) if (count[i] > 0) coveredY += ys[i+1] - ys[i];
            area += coveredY * (e[0] - prevX);
            prevX = e[0];
            int yLo = Arrays.binarySearch(ys, e[2]), yHi = Arrays.binarySearch(ys, e[3]);
            int delta = e[1] == 0 ? 1 : -1;
            for (int i = yLo; i < yHi; i++) count[i] += delta;
        }
        return area;
    }

    public static void main(String[] args) {
        Problem39_SweepLineRectangleUnionArea sol = new Problem39_SweepLineRectangleUnionArea();
        System.out.println(sol.rectangleUnionArea(new int[][]{{0,0,2,2},{1,1,3,3}})); // 7
    }
}
