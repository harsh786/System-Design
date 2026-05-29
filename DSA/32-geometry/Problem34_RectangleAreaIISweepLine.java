import java.util.*;

public class Problem34_RectangleAreaIISweepLine {
    public static int rectangleArea(int[][] rectangles) {
        int MOD = 1_000_000_007;
        Set<Integer> xSet = new TreeSet<>();
        for (int[] r : rectangles) { xSet.add(r[0]); xSet.add(r[2]); }
        Integer[] xs = xSet.toArray(new Integer[0]);
        Map<Integer, Integer> xIndex = new HashMap<>();
        for (int i = 0; i < xs.length; i++) xIndex.put(xs[i], i);
        List<int[]> events = new ArrayList<>();
        for (int[] r : rectangles) { events.add(new int[]{r[1], xIndex.get(r[0]), xIndex.get(r[2]), 1}); events.add(new int[]{r[3], xIndex.get(r[0]), xIndex.get(r[2]), -1}); }
        events.sort((a,b) -> a[0] - b[0]);
        int[] count = new int[xs.length];
        long ans = 0; int prevY = events.get(0)[0];
        for (int[] e : events) {
            int curY = e[0];
            long width = 0;
            for (int i = 0; i < xs.length - 1; i++) if (count[i] > 0) width += xs[i+1] - xs[i];
            ans = (ans + width * (curY - prevY)) % MOD;
            prevY = curY;
            for (int i = e[1]; i < e[2]; i++) count[i] += e[3];
        }
        return (int) ans;
    }
    public static void main(String[] args) {
        System.out.println(rectangleArea(new int[][]{{0,0,2,2},{1,0,2,3},{1,0,3,1}})); // 6
    }
}
