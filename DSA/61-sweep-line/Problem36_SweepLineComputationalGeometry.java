import java.util.*;

public class Problem36_SweepLineComputationalGeometry {
    /* Count rectangle intersections using sweep line */
    public int countIntersections(int[][] rects) {
        List<int[]> events = new ArrayList<>();
        for (int i = 0; i < rects.length; i++) {
            events.add(new int[]{rects[i][0], 0, i}); // start
            events.add(new int[]{rects[i][2], 1, i}); // end
        }
        events.sort((a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
        Set<Integer> active = new HashSet<>();
        int count = 0;
        for (int[] e : events) {
            if (e[1] == 0) {
                for (int idx : active) {
                    if (rects[idx][1] < rects[e[2]][3] && rects[idx][3] > rects[e[2]][1]) count++;
                }
                active.add(e[2]);
            } else active.remove(e[2]);
        }
        return count;
    }

    public static void main(String[] args) {
        Problem36_SweepLineComputationalGeometry sol = new Problem36_SweepLineComputationalGeometry();
        System.out.println(sol.countIntersections(new int[][]{{0,0,2,2},{1,1,3,3},{4,4,5,5}})); // 1
    }
}
