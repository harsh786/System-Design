package segmenttree;

import java.util.*;

/**
 * Problem 28: Online Majority Element in Subarray (LeetCode 1157)
 * 
 * Approach: Segment tree storing candidate majority element (Boyer-Moore voting per segment).
 * Query gives candidate, then verify using binary search on sorted indices.
 * 
 * Time Complexity: O(n) build, O(log^2 n) per query
 * Space Complexity: O(n)
 */
public class Problem28_OnlineMajorityElementInSubarray {
    
    private int[] cand, cnt, arr;
    private Map<Integer, List<Integer>> posMap;
    private int n;
    
    public Problem28_OnlineMajorityElementInSubarray(int[] arr) {
        this.arr = arr; n = arr.length;
        cand = new int[4 * n]; cnt = new int[4 * n];
        posMap = new HashMap<>();
        for (int i = 0; i < n; i++) posMap.computeIfAbsent(arr[i], k -> new ArrayList<>()).add(i);
        build(1, 0, n - 1);
    }
    
    private void build(int node, int s, int e) {
        if (s == e) { cand[node] = arr[s]; cnt[node] = 1; return; }
        int mid = (s + e) / 2;
        build(2 * node, s, mid); build(2 * node + 1, mid + 1, e);
        merge(node);
    }
    
    private void merge(int node) {
        int l = 2 * node, r = 2 * node + 1;
        if (cand[l] == cand[r]) { cand[node] = cand[l]; cnt[node] = cnt[l] + cnt[r]; }
        else if (cnt[l] >= cnt[r]) { cand[node] = cand[l]; cnt[node] = cnt[l] - cnt[r]; }
        else { cand[node] = cand[r]; cnt[node] = cnt[r] - cnt[l]; }
    }
    
    private int[] query(int node, int s, int e, int l, int r) {
        if (r < s || e < l) return new int[]{0, 0};
        if (l <= s && e <= r) return new int[]{cand[node], cnt[node]};
        int mid = (s + e) / 2;
        int[] left = query(2 * node, s, mid, l, r);
        int[] right = query(2 * node + 1, mid + 1, e, l, r);
        if (left[0] == right[0]) return new int[]{left[0], left[1] + right[1]};
        if (left[1] >= right[1]) return new int[]{left[0], left[1] - right[1]};
        return new int[]{right[0], right[1] - left[1]};
    }
    
    private int countInRange(int val, int l, int r) {
        List<Integer> pos = posMap.get(val);
        if (pos == null) return 0;
        int lo = Collections.binarySearch(pos, l); if (lo < 0) lo = -lo - 1;
        int hi = Collections.binarySearch(pos, r); if (hi < 0) hi = -hi - 2; else hi = hi;
        return hi - lo + 1;
    }
    
    public int query(int left, int right, int threshold) {
        int[] res = query(1, 0, n - 1, left, right);
        int candidate = res[0];
        if (countInRange(candidate, left, right) >= threshold) return candidate;
        return -1;
    }
    
    public static void main(String[] args) {
        Problem28_OnlineMajorityElementInSubarray sol = new Problem28_OnlineMajorityElementInSubarray(new int[]{1,1,2,2,1,1});
        System.out.println(sol.query(0, 5, 4)); // 1
        System.out.println(sol.query(2, 3, 2)); // -1
        System.out.println(sol.query(3, 5, 2)); // 1
    }
}
