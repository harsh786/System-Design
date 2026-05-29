import java.util.*;

public class Problem20_AmountOfNewAreaPainted {
    public int[] amountPainted(int[][] paint) {
        TreeMap<Integer, Integer> painted = new TreeMap<>();
        int[] res = new int[paint.length];
        for (int i = 0; i < paint.length; i++) {
            int start = paint[i][0], end = paint[i][1], area = 0;
            Map.Entry<Integer, Integer> entry = painted.floorEntry(start);
            if (entry != null && entry.getValue() >= start) { start = entry.getKey(); }
            while (true) {
                Map.Entry<Integer, Integer> next = painted.ceilingEntry(start);
                if (next == null || next.getKey() >= end) break;
                area -= Math.min(end, next.getValue()) - next.getKey();
                end = Math.max(end, next.getValue());
                painted.remove(next.getKey());
            }
            entry = painted.floorEntry(start);
            if (entry != null && entry.getValue() >= start) {
                area += end - Math.max(start, entry.getKey());
                area -= entry.getValue() - entry.getKey();
                painted.remove(entry.getKey());
                start = entry.getKey();
                end = Math.max(end, entry.getValue());
            }
            res[i] = end - start + area - (painted.containsKey(start) ? painted.get(start) - start : 0);
            // Simplified: just track new area
            int newArea = end - paint[i][0];
            // Recalculate properly
            res[i] = Math.max(0, end - Math.max(start, paint[i][0]));
            painted.put(start, end);
        }
        // Simpler approach
        return amountPaintedSimple(paint);
    }

    private int[] amountPaintedSimple(int[][] paint) {
        int[] res = new int[paint.length];
        TreeSet<Integer> unpainted = new TreeSet<>();
        int maxEnd = 0;
        for (int[] p : paint) maxEnd = Math.max(maxEnd, p[1]);
        for (int i = 0; i < maxEnd; i++) unpainted.add(i);
        for (int i = 0; i < paint.length; i++) {
            Integer pos = unpainted.ceiling(paint[i][0]);
            while (pos != null && pos < paint[i][1]) {
                res[i]++;
                unpainted.remove(pos);
                pos = unpainted.ceiling(paint[i][0]);
            }
        }
        return res;
    }

    public static void main(String[] args) {
        Problem20_AmountOfNewAreaPainted sol = new Problem20_AmountOfNewAreaPainted();
        System.out.println(Arrays.toString(sol.amountPainted(new int[][]{{1,4},{4,7},{5,8}})));
    }
}
