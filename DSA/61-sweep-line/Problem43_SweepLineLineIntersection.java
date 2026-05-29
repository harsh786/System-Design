import java.util.*;

public class Problem43_SweepLineLineIntersection {
    /* Count intersections among horizontal and vertical line segments */
    public int countIntersections(int[][] hSegments, int[][] vSegments) {
        List<int[]> events = new ArrayList<>();
        for (int[] h : hSegments) { events.add(new int[]{h[0], 0, h[2], 0}); events.add(new int[]{h[1], 2, h[2], 0}); }
        for (int[] v : vSegments) { events.add(new int[]{v[0], 1, v[2], v[3]}); }
        events.sort((a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
        TreeMap<Integer, Integer> activeY = new TreeMap<>();
        int count = 0;
        for (int[] e : events) {
            if (e[1] == 0) activeY.merge(e[2], 1, Integer::sum);
            else if (e[1] == 2) { activeY.merge(e[2], -1, Integer::sum); if (activeY.get(e[2]) == 0) activeY.remove(e[2]); }
            else count += activeY.subMap(Math.min(e[2],e[3]), true, Math.max(e[2],e[3]), true).size();
        }
        return count;
    }

    public static void main(String[] args) {
        Problem43_SweepLineLineIntersection sol = new Problem43_SweepLineLineIntersection();
        // h: [x1,x2,y], v: [x,y1,y2]  (reusing as [x,0,y1,y2])
        System.out.println(sol.countIntersections(new int[][]{{1,5,3},{1,5,5}}, new int[][]{{3,1,1,6}})); // 2
    }
}
