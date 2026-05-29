import java.util.*;

public class Problem43_EuclideanDistanceProblems {
    // K closest points using quickselect
    public static int[][] kClosest(int[][] points, int k) {
        quickSelect(points, 0, points.length - 1, k);
        return Arrays.copyOf(points, k);
    }
    static void quickSelect(int[][] pts, int l, int r, int k) {
        if (l >= r) return;
        int pivot = dist2(pts[r]), i = l;
        for (int j = l; j < r; j++) if (dist2(pts[j]) < pivot) { swap(pts, i, j); i++; }
        swap(pts, i, r);
        if (i == k) return;
        if (i < k) quickSelect(pts, i+1, r, k);
        else quickSelect(pts, l, i-1, k);
    }
    static int dist2(int[] p) { return p[0]*p[0]+p[1]*p[1]; }
    static void swap(int[][] pts, int a, int b) { int[] t = pts[a]; pts[a] = pts[b]; pts[b] = t; }
    public static void main(String[] args) {
        int[][] res = kClosest(new int[][]{{3,3},{5,-1},{-2,4}}, 2);
        for (int[] p : res) System.out.println(Arrays.toString(p));
    }
}
