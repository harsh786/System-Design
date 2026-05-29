import java.util.*;

public class Problem05_RandomPointInNonOverlappingRectangles {
    // Weighted pick rectangle then uniform point in it
    int[][] rects;
    int[] prefixAreas;
    int totalArea;
    Random rand;

    public Problem05_RandomPointInNonOverlappingRectangles(int[][] rects) {
        this.rects = rects;
        prefixAreas = new int[rects.length];
        for (int i = 0; i < rects.length; i++) {
            int area = (rects[i][2] - rects[i][0] + 1) * (rects[i][3] - rects[i][1] + 1);
            prefixAreas[i] = (i == 0 ? 0 : prefixAreas[i-1]) + area;
        }
        totalArea = prefixAreas[rects.length - 1];
        rand = new Random();
    }

    public int[] pick() {
        int target = rand.nextInt(totalArea) + 1;
        int lo = 0, hi = rects.length - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (prefixAreas[mid] < target) lo = mid + 1;
            else hi = mid;
        }
        int[] r = rects[lo];
        int x = r[0] + rand.nextInt(r[2] - r[0] + 1);
        int y = r[1] + rand.nextInt(r[3] - r[1] + 1);
        return new int[]{x, y};
    }

    public static void main(String[] args) {
        int[][] rects = {{-2,-2,1,1},{2,2,4,6}};
        Problem05_RandomPointInNonOverlappingRectangles sol = new Problem05_RandomPointInNonOverlappingRectangles(rects);
        for (int i = 0; i < 5; i++) System.out.println(Arrays.toString(sol.pick()));
    }
}
