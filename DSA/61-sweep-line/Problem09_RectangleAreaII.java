import java.util.*;

public class Problem09_RectangleAreaII {
    static final int MOD = 1_000_000_007;

    public int rectangleArea(int[][] rectangles) {
        Set<Integer> xSet = new TreeSet<>(), ySet = new TreeSet<>();
        for (int[] r : rectangles) { xSet.add(r[0]); xSet.add(r[2]); ySet.add(r[1]); ySet.add(r[3]); }
        Integer[] xs = xSet.toArray(new Integer[0]), ys = ySet.toArray(new Integer[0]);
        Map<Integer, Integer> xi = new HashMap<>(), yi = new HashMap<>();
        for (int i = 0; i < xs.length; i++) xi.put(xs[i], i);
        for (int i = 0; i < ys.length; i++) yi.put(ys[i], i);
        boolean[][] grid = new boolean[xs.length][ys.length];
        for (int[] r : rectangles) {
            for (int x = xi.get(r[0]); x < xi.get(r[2]); x++)
                for (int y = yi.get(r[1]); y < yi.get(r[3]); y++) grid[x][y] = true;
        }
        long area = 0;
        for (int x = 0; x < xs.length - 1; x++)
            for (int y = 0; y < ys.length - 1; y++)
                if (grid[x][y]) area = (area + (long)(xs[x+1]-xs[x]) * (ys[y+1]-ys[y])) % MOD;
        return (int) area;
    }

    public static void main(String[] args) {
        Problem09_RectangleAreaII sol = new Problem09_RectangleAreaII();
        System.out.println(sol.rectangleArea(new int[][]{{0,0,2,2},{1,0,2,3},{1,0,3,1}})); // 6
    }
}
