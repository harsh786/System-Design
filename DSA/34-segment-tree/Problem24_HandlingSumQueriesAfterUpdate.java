package segmenttree;

/**
 * Problem 24: Handling Sum Queries After Update (LeetCode 2569)
 * 
 * Approach: Segment tree with lazy flip on nums1. Track count of 1s.
 * For type 2, sum of nums2 += val * count_of_ones_in_nums1.
 * 
 * Time Complexity: O(n + q*log n)
 * Space Complexity: O(n)
 */
public class Problem24_HandlingSumQueriesAfterUpdate {
    
    private int[] tree;
    private boolean[] flip;
    private int n;
    
    public long[] handleQuery(int[] nums1, int[] nums2, int[][] queries) {
        n = nums1.length;
        tree = new int[4 * n]; flip = new boolean[4 * n];
        build(1, 0, n - 1, nums1);
        long sum2 = 0;
        for (int v : nums2) sum2 += v;
        
        java.util.List<Long> res = new java.util.ArrayList<>();
        for (int[] q : queries) {
            if (q[0] == 1) flipRange(1, 0, n - 1, q[1], q[2]);
            else if (q[0] == 2) sum2 += (long) q[1] * tree[1];
            else res.add(sum2);
        }
        return res.stream().mapToLong(Long::longValue).toArray();
    }
    
    private void build(int node, int s, int e, int[] arr) {
        if (s == e) { tree[node] = arr[s]; return; }
        int mid = (s + e) / 2;
        build(2 * node, s, mid, arr); build(2 * node + 1, mid + 1, e, arr);
        tree[node] = tree[2 * node] + tree[2 * node + 1];
    }
    
    private void pushDown(int node, int s, int e) {
        if (flip[node]) {
            int mid = (s + e) / 2;
            applyFlip(2 * node, s, mid); applyFlip(2 * node + 1, mid + 1, e);
            flip[node] = false;
        }
    }
    
    private void applyFlip(int node, int s, int e) {
        tree[node] = (e - s + 1) - tree[node];
        flip[node] = !flip[node];
    }
    
    private void flipRange(int node, int s, int e, int l, int r) {
        if (r < s || e < l) return;
        if (l <= s && e <= r) { applyFlip(node, s, e); return; }
        pushDown(node, s, e);
        int mid = (s + e) / 2;
        flipRange(2 * node, s, mid, l, r); flipRange(2 * node + 1, mid + 1, e, l, r);
        tree[node] = tree[2 * node] + tree[2 * node + 1];
    }
    
    public static void main(String[] args) {
        Problem24_HandlingSumQueriesAfterUpdate sol = new Problem24_HandlingSumQueriesAfterUpdate();
        long[] res = sol.handleQuery(new int[]{1,0,1}, new int[]{0,0,0}, new int[][]{{1,1,1},{2,1,0},{3,0,0}});
        for (long v : res) System.out.print(v + " "); // 2
        System.out.println();
    }
}
