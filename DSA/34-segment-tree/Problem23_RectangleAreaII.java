package segmenttree;

import java.util.*;

/**
 * Problem 23: Rectangle Area II (LeetCode 850)
 * 
 * Approach: Sweep line + segment tree. Sweep vertical lines, use segment tree to track
 * covered length on y-axis. Coordinate compress y values.
 * 
 * Time Complexity: O(n^2 log n) or O(n log n) with proper segment tree
 * Space Complexity: O(n)
 */
public class Problem23_RectangleAreaII {
    
    private static final int MOD = 1_000_000_007;
    
    public int rectangleArea(int[][] rectangles) {
        // Collect y coordinates
        TreeSet<Integer> ySet = new TreeSet<>();
        List<int[]> events = new ArrayList<>();
        for (int[] r : rectangles) {
            ySet.add(r[1]); ySet.add(r[3]);
            events.add(new int[]{r[0], 0, r[1], r[3]}); // open
            events.add(new int[]{r[2], 1, r[1], r[3]}); // close
        }
        events.sort((a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
        
        Integer[] ys = ySet.toArray(new Integer[0]);
        Map<Integer, Integer> yIdx = new HashMap<>();
        for (int i = 0; i < ys.length; i++) yIdx.put(ys[i], i);
        
        int n = ys.length - 1; // number of segments
        int[] cnt = new int[4 * n];
        long[] len = new long[4 * n];
        
        long ans = 0;
        int prevX = events.get(0)[0];
        for (int[] e : events) {
            int curX = e[0];
            ans = (ans + len[1] * (curX - prevX)) % MOD;
            prevX = curX;
            int lo = yIdx.get(e[2]), hi = yIdx.get(e[3]) - 1;
            if (e[1] == 0) update(1, 0, n - 1, lo, hi, 1, cnt, len, ys);
            else update(1, 0, n - 1, lo, hi, -1, cnt, len, ys);
        }
        return (int) ans;
    }
    
    private void update(int node, int s, int e, int l, int r, int val, int[] cnt, long[] len, Integer[] ys) {
        if (r < s || e < l) return;
        if (l <= s && e <= r) { cnt[node] += val; }
        else {
            int mid = (s + e) / 2;
            update(2 * node, s, mid, l, r, val, cnt, len, ys);
            update(2 * node + 1, mid + 1, e, l, r, val, cnt, len, ys);
        }
        if (cnt[node] > 0) len[node] = ys[e + 1] - ys[s];
        else if (s == e) len[node] = 0;
        else len[node] = len[2 * node] + len[2 * node + 1];
    }
    
    public static void main(String[] args) {
        Problem23_RectangleAreaII sol = new Problem23_RectangleAreaII();
        System.out.println(sol.rectangleArea(new int[][]{{0,0,2,2},{1,0,2,3},{1,0,3,1}})); // 6
    }
}
