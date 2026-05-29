import java.util.*;

public class Problem48_ResourceContentionDetection {
    public List<int[]> findContentions(int[][] accesses, int threshold) {
        TreeMap<Integer, Integer> sweep = new TreeMap<>();
        for (int[] a : accesses) { sweep.merge(a[0], 1, Integer::sum); sweep.merge(a[1], -1, Integer::sum); }
        List<int[]> contentions = new ArrayList<>();
        int cur = 0, start = -1;
        for (Map.Entry<Integer, Integer> e : sweep.entrySet()) {
            int prev = cur; cur += e.getValue();
            if (prev < threshold && cur >= threshold) start = e.getKey();
            else if (prev >= threshold && cur < threshold) contentions.add(new int[]{start, e.getKey()});
        }
        return contentions;
    }

    public static void main(String[] args) {
        Problem48_ResourceContentionDetection sol = new Problem48_ResourceContentionDetection();
        List<int[]> res = sol.findContentions(new int[][]{{0,10},{5,15},{8,12},{11,20}}, 3);
        for (int[] r : res) System.out.println(Arrays.toString(r));
    }
}
