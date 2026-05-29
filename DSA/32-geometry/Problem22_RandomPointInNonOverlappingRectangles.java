import java.util.*;

public class Problem22_RandomPointInNonOverlappingRectangles {
    int[][] rects; int[] prefixSum; Random rand = new Random(); int total;
    public Problem22_RandomPointInNonOverlappingRectangles(int[][] rects) {
        this.rects = rects; prefixSum = new int[rects.length];
        for (int i = 0; i < rects.length; i++) {
            int area = (rects[i][2] - rects[i][0] + 1) * (rects[i][3] - rects[i][1] + 1);
            prefixSum[i] = (i > 0 ? prefixSum[i-1] : 0) + area;
        }
        total = prefixSum[rects.length - 1];
    }
    public int[] pick() {
        int target = rand.nextInt(total);
        int lo = 0, hi = rects.length - 1;
        while (lo < hi) { int mid = (lo+hi)/2; if (prefixSum[mid] <= target) lo = mid+1; else hi = mid; }
        int[] r = rects[lo];
        return new int[]{r[0] + rand.nextInt(r[2]-r[0]+1), r[1] + rand.nextInt(r[3]-r[1]+1)};
    }
    public static void main(String[] args) {
        Problem22_RandomPointInNonOverlappingRectangles sol = new Problem22_RandomPointInNonOverlappingRectangles(new int[][]{{-2,-2,1,1},{2,2,4,6}});
        System.out.println(Arrays.toString(sol.pick()));
    }
}
