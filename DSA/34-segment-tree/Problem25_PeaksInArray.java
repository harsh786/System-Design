package segmenttree;

/**
 * Problem 25: Peaks in Array (LeetCode 2951)
 * 
 * Approach: A peak is arr[i] > arr[i-1] && arr[i] > arr[i+1]. Use segment tree to count peaks in range.
 * On update, recheck at most 3 positions (idx-1, idx, idx+1).
 * 
 * Time Complexity: O((n + q) log n)
 * Space Complexity: O(n)
 */
public class Problem25_PeaksInArray {
    
    private int[] tree, arr;
    private int n;
    
    private boolean isPeak(int i) {
        return i > 0 && i < n - 1 && arr[i] > arr[i - 1] && arr[i] > arr[i + 1];
    }
    
    public java.util.List<Integer> countOfPeaks(int[] nums, int[][] queries) {
        n = nums.length; arr = nums;
        tree = new int[4 * n];
        build(1, 0, n - 1);
        java.util.List<Integer> res = new java.util.ArrayList<>();
        for (int[] q : queries) {
            if (q[0] == 1) {
                res.add(q[1] + 1 <= q[2] - 1 ? query(1, 0, n - 1, q[1] + 1, q[2] - 1) : 0);
            } else {
                arr[q[1]] = q[2];
                for (int i = q[1] - 1; i <= q[1] + 1; i++)
                    if (i >= 1 && i < n - 1) updatePoint(1, 0, n - 1, i, isPeak(i) ? 1 : 0);
            }
        }
        return res;
    }
    
    private void build(int node, int s, int e) {
        if (s == e) { tree[node] = isPeak(s) ? 1 : 0; return; }
        int mid = (s + e) / 2;
        build(2 * node, s, mid); build(2 * node + 1, mid + 1, e);
        tree[node] = tree[2 * node] + tree[2 * node + 1];
    }
    
    private void updatePoint(int node, int s, int e, int idx, int val) {
        if (s == e) { tree[node] = val; return; }
        int mid = (s + e) / 2;
        if (idx <= mid) updatePoint(2 * node, s, mid, idx, val);
        else updatePoint(2 * node + 1, mid + 1, e, idx, val);
        tree[node] = tree[2 * node] + tree[2 * node + 1];
    }
    
    private int query(int node, int s, int e, int l, int r) {
        if (r < s || e < l) return 0;
        if (l <= s && e <= r) return tree[node];
        int mid = (s + e) / 2;
        return query(2 * node, s, mid, l, r) + query(2 * node + 1, mid + 1, e, l, r);
    }
    
    public static void main(String[] args) {
        Problem25_PeaksInArray sol = new Problem25_PeaksInArray();
        var res = sol.countOfPeaks(new int[]{3,1,4,2,5}, new int[][]{{1,0,4},{2,3,6},{1,0,4}});
        System.out.println(res); // [2, 2] or similar
    }
}
