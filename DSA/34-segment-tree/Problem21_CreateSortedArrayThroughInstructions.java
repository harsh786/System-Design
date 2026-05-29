package segmenttree;

/**
 * Problem 21: Create Sorted Array through Instructions (LeetCode 1649)
 * 
 * Approach: Use segment tree (BIT-like) on value range to count elements less than and greater than current.
 * Cost = min(strictly_less, strictly_greater).
 * 
 * Time Complexity: O(n log m) where m = max value
 * Space Complexity: O(m)
 */
public class Problem21_CreateSortedArrayThroughInstructions {
    
    private int[] tree;
    private int size;
    private static final int MOD = 1_000_000_007;
    
    public int createSortedArray(int[] instructions) {
        size = 100001;
        tree = new int[4 * size];
        long cost = 0;
        for (int i = 0; i < instructions.length; i++) {
            int val = instructions[i];
            int less = query(1, 0, size - 1, 0, val - 1);
            int greater = query(1, 0, size - 1, val + 1, size - 1);
            cost = (cost + Math.min(less, greater)) % MOD;
            update(1, 0, size - 1, val);
        }
        return (int) cost;
    }
    
    private void update(int node, int s, int e, int idx) {
        if (s == e) { tree[node]++; return; }
        int mid = (s + e) / 2;
        if (idx <= mid) update(2 * node, s, mid, idx);
        else update(2 * node + 1, mid + 1, e, idx);
        tree[node] = tree[2 * node] + tree[2 * node + 1];
    }
    
    private int query(int node, int s, int e, int l, int r) {
        if (l > r || r < s || e < l) return 0;
        if (l <= s && e <= r) return tree[node];
        int mid = (s + e) / 2;
        return query(2 * node, s, mid, l, r) + query(2 * node + 1, mid + 1, e, l, r);
    }
    
    public static void main(String[] args) {
        Problem21_CreateSortedArrayThroughInstructions sol = new Problem21_CreateSortedArrayThroughInstructions();
        System.out.println(sol.createSortedArray(new int[]{1,5,6,2})); // 1
        sol = new Problem21_CreateSortedArrayThroughInstructions();
        System.out.println(sol.createSortedArray(new int[]{1,2,3,6,5,4})); // 3
    }
}
