package segmenttree;

import java.util.*;

/**
 * Problem 36: Segment Tree for Sweep Line Area (Union of Rectangles)
 * 
 * Approach: Sweep line on x-axis, segment tree on y-axis tracking covered length.
 * Same concept as Rectangle Area II but standalone template.
 * 
 * Time Complexity: O(n log n)
 * Space Complexity: O(n)
 */
public class Problem36_SegmentTreeForSweepLineArea {
    
    private int[] cnt;
    private double[] len;
    private double[] ys;
    
    public double unionArea(double[][] rects) {
        List<double[]> events = new ArrayList<>();
        TreeSet<Double> ySet = new TreeSet<>();
        for (double[] r : rects) {
            ySet.add(r[1]); ySet.add(r[3]);
            events.add(new double[]{r[0], 1, r[1], r[3]});
            events.add(new double[]{r[2], -1, r[1], r[3]});
        }
        events.sort((a, b) -> Double.compare(a[0], b[0]));
        ys = new double[ySet.size()];
        int i = 0; for (double y : ySet) ys[i++] = y;
        int n = ys.length - 1;
        cnt = new int[4 * n]; len = new double[4 * n];
        
        double area = 0, prevX = events.get(0)[0];
        for (double[] e : events) {
            area += len[1] * (e[0] - prevX);
            prevX = e[0];
            int lo = Arrays.binarySearch(ys, e[2]);
            int hi = Arrays.binarySearch(ys, e[3]) - 1;
            update(1, 0, n - 1, lo, hi, (int) e[1]);
        }
        return area;
    }
    
    private void update(int o, int s, int e, int l, int r, int val) {
        if (r < s || e < l) return;
        if (l <= s && e <= r) cnt[o] += val;
        else {
            int mid = (s + e) / 2;
            update(2 * o, s, mid, l, r, val);
            update(2 * o + 1, mid + 1, e, l, r, val);
        }
        if (cnt[o] > 0) len[o] = ys[e + 1] - ys[s];
        else if (s == e) len[o] = 0;
        else len[o] = len[2 * o] + len[2 * o + 1];
    }
    
    public static void main(String[] args) {
        Problem36_SegmentTreeForSweepLineArea sol = new Problem36_SegmentTreeForSweepLineArea();
        // Two overlapping rectangles
        double area = sol.unionArea(new double[][]{{0,0,2,2},{1,1,3,3}});
        System.out.printf("%.1f%n", area); // 7.0
    }
}
