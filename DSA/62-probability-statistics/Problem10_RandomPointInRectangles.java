import java.util.*;

public class Problem10_RandomPointInRectangles {
    private int[][] rects;
    private int[] prefix;
    private Random rand = new Random();

    public Problem10_RandomPointInRectangles(int[][] rects) {
        this.rects = rects;
        prefix = new int[rects.length];
        prefix[0] = (rects[0][2]-rects[0][0]+1) * (rects[0][3]-rects[0][1]+1);
        for (int i = 1; i < rects.length; i++)
            prefix[i] = prefix[i-1] + (rects[i][2]-rects[i][0]+1) * (rects[i][3]-rects[i][1]+1);
    }

    public int[] pick() {
        int target = rand.nextInt(prefix[prefix.length-1]) + 1;
        int lo = 0, hi = prefix.length - 1;
        while (lo < hi) { int mid = (lo+hi)/2; if (prefix[mid] < target) lo = mid+1; else hi = mid; }
        int[] r = rects[lo];
        return new int[]{r[0] + rand.nextInt(r[2]-r[0]+1), r[1] + rand.nextInt(r[3]-r[1]+1)};
    }

    public static void main(String[] args) {
        Problem10_RandomPointInRectangles sol = new Problem10_RandomPointInRectangles(new int[][]{{-2,-2,1,1},{2,2,4,6}});
        for (int i = 0; i < 5; i++) System.out.println(Arrays.toString(sol.pick()));
    }
}
