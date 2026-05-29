import java.util.*;

public class Problem46_AmountOfNewAreaPaintedEachDay {
    // LC 2158: Each day paint [start, end), return new area painted each day
    public static int[] amountPainted(int[][] paint) {
        TreeMap<Integer, Integer> map = new TreeMap<>();
        int[] result = new int[paint.length];
        for (int i = 0; i < paint.length; i++) {
            int start = paint[i][0], end = paint[i][1], painted = 0;
            Integer key = map.floorKey(start);
            if (key != null && map.get(key) > start) { start = key; }
            else key = start;

            // Merge overlapping intervals and count new area
            Integer cur = map.ceilingKey(start);
            int newStart = paint[i][0], newEnd = paint[i][1];
            int totalNew = newEnd - newStart;
            cur = map.floorKey(newEnd);
            // Simpler approach: iterate and remove covered intervals
            start = paint[i][0]; end = paint[i][1];
            Integer lo = map.floorKey(start);
            if (lo != null && map.get(lo) >= start) start = lo;
            else lo = null;

            NavigableMap<Integer, Integer> sub = map.subMap(
                lo != null ? lo : map.ceilingKey(start) != null ? map.ceilingKey(start) : end,
                true, end, false);
            int covered = 0;
            List<Integer> toRemove = new ArrayList<>(sub.keySet());
            for (int k2 : toRemove) {
                int e2 = map.get(k2);
                covered += Math.min(e2, end) - Math.max(k2, paint[i][0]);
                end = Math.max(end, e2);
                start = Math.min(start, k2);
                map.remove(k2);
            }
            // Check floor key once more
            Integer fl = map.floorKey(paint[i][0]);
            if (fl != null && map.get(fl) >= paint[i][0]) {
                covered += Math.min(map.get(fl), paint[i][1]) - paint[i][0];
                end = Math.max(end, map.get(fl));
                start = Math.min(start, fl);
                map.remove(fl);
            }
            map.put(start, end);
            result[i] = (paint[i][1] - paint[i][0]) - covered;
            if (result[i] < 0) result[i] = 0;
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(amountPainted(new int[][]{{1,4},{4,7},{5,8}})));
        // [3, 3, 1]
    }
}
