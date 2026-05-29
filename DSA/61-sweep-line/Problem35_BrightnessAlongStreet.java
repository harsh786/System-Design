import java.util.*;

public class Problem35_BrightnessAlongStreet {
    /* Each light at position p illuminates [p-r, p+r]. Find brightest point. */
    public int brightestPoint(int[][] lights) {
        TreeMap<Integer, Integer> sweep = new TreeMap<>();
        for (int[] l : lights) { sweep.merge(l[0] - l[1], 1, Integer::sum); sweep.merge(l[0] + l[1] + 1, -1, Integer::sum); }
        int max = 0, cur = 0, point = 0;
        for (Map.Entry<Integer, Integer> e : sweep.entrySet()) {
            cur += e.getValue();
            if (cur > max) { max = cur; point = e.getKey(); }
        }
        return point;
    }

    public static void main(String[] args) {
        Problem35_BrightnessAlongStreet sol = new Problem35_BrightnessAlongStreet();
        System.out.println(sol.brightestPoint(new int[][]{{-3,2},{1,2},{3,3}}));
    }
}
