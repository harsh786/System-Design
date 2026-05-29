package segmenttree;

import java.util.function.BinaryOperator;

/**
 * Problem 50: Segment Tree Generic Template
 * 
 * A generic segment tree that works with any associative combine operation.
 * 
 * Time Complexity: O(n) build, O(log n) update/query
 * Space Complexity: O(n)
 */
public class Problem50_SegmentTreeGenericTemplate<T> {
    
    private Object[] tree;
    private int n;
    private BinaryOperator<T> combine;
    private T identity;
    
    @SuppressWarnings("unchecked")
    public Problem50_SegmentTreeGenericTemplate(T[] arr, BinaryOperator<T> combine, T identity) {
        this.n = arr.length; this.combine = combine; this.identity = identity;
        tree = new Object[4 * n];
        build(1, 0, n-1, arr);
    }
    
    private void build(int o, int s, int e, T[] arr) {
        if (s == e) { tree[o] = arr[s]; return; }
        int mid = (s+e)/2;
        build(2*o, s, mid, arr); build(2*o+1, mid+1, e, arr);
        tree[o] = combine.apply(get(2*o), get(2*o+1));
    }
    
    @SuppressWarnings("unchecked")
    private T get(int idx) { return tree[idx] == null ? identity : (T) tree[idx]; }
    
    public void update(int idx, T val) { update(1, 0, n-1, idx, val); }
    
    private void update(int o, int s, int e, int idx, T val) {
        if (s == e) { tree[o] = val; return; }
        int mid = (s+e)/2;
        if (idx <= mid) update(2*o, s, mid, idx, val);
        else update(2*o+1, mid+1, e, idx, val);
        tree[o] = combine.apply(get(2*o), get(2*o+1));
    }
    
    public T query(int l, int r) { return query(1, 0, n-1, l, r); }
    
    private T query(int o, int s, int e, int l, int r) {
        if (r < s || e < l) return identity;
        if (l <= s && e <= r) return get(o);
        int mid = (s+e)/2;
        return combine.apply(query(2*o, s, mid, l, r), query(2*o+1, mid+1, e, l, r));
    }
    
    public static void main(String[] args) {
        // Sum segment tree
        Integer[] arr = {1, 2, 3, 4, 5};
        Problem50_SegmentTreeGenericTemplate<Integer> sumTree = new Problem50_SegmentTreeGenericTemplate<>(arr, Integer::sum, 0);
        System.out.println(sumTree.query(0, 4)); // 15
        sumTree.update(2, 10);
        System.out.println(sumTree.query(0, 4)); // 22
        
        // Min segment tree
        Problem50_SegmentTreeGenericTemplate<Integer> minTree = new Problem50_SegmentTreeGenericTemplate<>(arr, Math::min, Integer.MAX_VALUE);
        System.out.println(minTree.query(0, 4)); // 1
        
        // Max segment tree
        Problem50_SegmentTreeGenericTemplate<Integer> maxTree = new Problem50_SegmentTreeGenericTemplate<>(arr, Math::max, Integer.MIN_VALUE);
        System.out.println(maxTree.query(0, 4)); // 5
    }
}
