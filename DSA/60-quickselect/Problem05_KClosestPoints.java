import java.util.*;

public class Problem05_KClosestPoints {
    /*
     * K Closest Points to Origin using Quickselect
     * Time: O(n) average
     */
    public int[][] kClosest(int[][] points, int k) {
        quickselect(points, 0, points.length - 1, k - 1);
        return Arrays.copyOfRange(points, 0, k);
    }

    private void quickselect(int[][] pts, int lo, int hi, int k) {
        if (lo >= hi) return;
        int pi = partition(pts, lo, hi);
        if (pi == k) return;
        else if (pi < k) quickselect(pts, pi + 1, hi, k);
        else quickselect(pts, lo, pi - 1, k);
    }

    private int partition(int[][] pts, int lo, int hi) {
        long pivot = dist(pts[hi]);
        int s = lo;
        for (int i = lo; i < hi; i++) {
            if (dist(pts[i]) <= pivot) { swap(pts, s, i); s++; }
        }
        swap(pts, s, hi);
        return s;
    }

    private long dist(int[] p) { return (long)p[0]*p[0] + (long)p[1]*p[1]; }
    private void swap(int[][] a, int i, int j) { int[] t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem05_KClosestPoints sol = new Problem05_KClosestPoints();
        int[][] res = sol.kClosest(new int[][]{{1,3},{-2,2},{5,8},{0,1}}, 2);
        for (int[] p : res) System.out.println(Arrays.toString(p));
    }
}
