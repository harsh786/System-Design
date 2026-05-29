package segmenttree;

/**
 * Problem 12: Longest Increasing Subsequence II (LeetCode 2407)
 * 
 * Approach: Segment tree on value range to query max LIS length ending with values in [nums[i]-k, nums[i]-1].
 * Update position nums[i] with the new LIS length.
 * 
 * Time Complexity: O(n log m) where m is max value
 * Space Complexity: O(m)
 */
public class Problem12_LongestIncreasingSubsequenceII {
    
    private int[] tree;
    private int n;
    
    public int lengthOfLIS(int[] nums, int k) {
        int maxVal = 0;
        for (int num : nums) maxVal = Math.max(maxVal, num);
        n = maxVal + 1;
        tree = new int[4 * n];
        int ans = 0;
        for (int num : nums) {
            int left = Math.max(0, num - k);
            int right = num - 1;
            int best = (left <= right) ? query(1, 0, n - 1, left, right) : 0;
            int cur = best + 1;
            ans = Math.max(ans, cur);
            update(1, 0, n - 1, num, cur);
        }
        return ans;
    }
    
    private void update(int node, int start, int end, int idx, int val) {
        if (start == end) { tree[node] = Math.max(tree[node], val); return; }
        int mid = (start + end) / 2;
        if (idx <= mid) update(2 * node, start, mid, idx, val);
        else update(2 * node + 1, mid + 1, end, idx, val);
        tree[node] = Math.max(tree[2 * node], tree[2 * node + 1]);
    }
    
    private int query(int node, int start, int end, int l, int r) {
        if (r < start || end < l) return 0;
        if (l <= start && end <= r) return tree[node];
        int mid = (start + end) / 2;
        return Math.max(query(2 * node, start, mid, l, r), query(2 * node + 1, mid + 1, end, l, r));
    }
    
    public static void main(String[] args) {
        Problem12_LongestIncreasingSubsequenceII sol = new Problem12_LongestIncreasingSubsequenceII();
        System.out.println(sol.lengthOfLIS(new int[]{4, 2, 1, 4, 3, 4, 5, 8, 15}, 3)); // 5
        System.out.println(sol.lengthOfLIS(new int[]{7, 4, 5, 1, 8, 12, 4, 7}, 5)); // 4
    }
}
