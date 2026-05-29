package segmenttree;

import java.util.*;

/**
 * Problem 26: Maximum Sum Queries (LeetCode 2736)
 * 
 * Approach: Sort queries and points by x descending. Process queries offline.
 * Use segment tree on compressed y-values storing max(x+y).
 * 
 * Time Complexity: O((n+q) log n)
 * Space Complexity: O(n+q)
 */
public class Problem26_MaximumSumQueries {
    
    private int[] tree;
    
    public int[] maximumSumQueries(int[] nums1, int[] nums2, int[][] queries) {
        int n = nums1.length, q = queries.length;
        int[][] pairs = new int[n][2];
        for (int i = 0; i < n; i++) { pairs[i][0] = nums1[i]; pairs[i][1] = nums2[i]; }
        Arrays.sort(pairs, (a, b) -> b[0] - a[0]);
        
        int[][] qs = new int[q][3];
        for (int i = 0; i < q; i++) { qs[i][0] = queries[i][0]; qs[i][1] = queries[i][1]; qs[i][2] = i; }
        Arrays.sort(qs, (a, b) -> b[0] - a[0]);
        
        // Compress y values
        TreeSet<Integer> ySet = new TreeSet<>();
        for (int[] p : pairs) ySet.add(p[1]);
        for (int[] qr : queries) ySet.add(qr[1]);
        Map<Integer, Integer> yMap = new HashMap<>();
        int idx = 0;
        for (int y : ySet) yMap.put(y, idx++);
        int sz = ySet.size();
        tree = new int[4 * sz];
        Arrays.fill(tree, -1);
        
        int[] ans = new int[q];
        int j = 0;
        for (int[] qr : qs) {
            while (j < n && pairs[j][0] >= qr[0]) {
                int yIdx = yMap.get(pairs[j][1]);
                update(1, 0, sz - 1, yIdx, pairs[j][0] + pairs[j][1]);
                j++;
            }
            int yIdx = yMap.get(qr[1]);
            ans[qr[2]] = query(1, 0, sz - 1, yIdx, sz - 1);
        }
        return ans;
    }
    
    private void update(int node, int s, int e, int idx, int val) {
        if (s == e) { tree[node] = Math.max(tree[node], val); return; }
        int mid = (s + e) / 2;
        if (idx <= mid) update(2 * node, s, mid, idx, val);
        else update(2 * node + 1, mid + 1, e, idx, val);
        tree[node] = Math.max(tree[2 * node], tree[2 * node + 1]);
    }
    
    private int query(int node, int s, int e, int l, int r) {
        if (r < s || e < l) return -1;
        if (l <= s && e <= r) return tree[node];
        int mid = (s + e) / 2;
        return Math.max(query(2 * node, s, mid, l, r), query(2 * node + 1, mid + 1, e, l, r));
    }
    
    public static void main(String[] args) {
        Problem26_MaximumSumQueries sol = new Problem26_MaximumSumQueries();
        int[] res = sol.maximumSumQueries(new int[]{4,3,1,2}, new int[]{2,4,9,5}, new int[][]{{4,1},{1,3},{2,5}});
        System.out.println(Arrays.toString(res)); // [6, 10, 7]
    }
}
