package segmenttree;

/**
 * Problem 34: Segment Tree for Hotel Queries (CSES)
 * 
 * Approach: Each hotel has rooms. For each group, find leftmost hotel with enough rooms.
 * Segment tree stores max available rooms; walk the tree to find leftmost sufficient hotel.
 * 
 * Time Complexity: O(log n) per query
 * Space Complexity: O(n)
 */
public class Problem34_SegmentTreeForHotelQueries {
    
    private int[] tree;
    private int n;
    
    public Problem34_SegmentTreeForHotelQueries(int[] rooms) {
        n = rooms.length; tree = new int[4 * n];
        build(1, 0, n - 1, rooms);
    }
    
    private void build(int o, int s, int e, int[] arr) {
        if (s == e) { tree[o] = arr[s]; return; }
        int mid = (s + e) / 2;
        build(2 * o, s, mid, arr); build(2 * o + 1, mid + 1, e, arr);
        tree[o] = Math.max(tree[2 * o], tree[2 * o + 1]);
    }
    
    // Find leftmost hotel with >= groupSize rooms, assign them, return hotel index (0-based) or -1
    public int assign(int groupSize) {
        if (tree[1] < groupSize) return -1;
        return assign(1, 0, n - 1, groupSize);
    }
    
    private int assign(int o, int s, int e, int groupSize) {
        if (s == e) { tree[o] -= groupSize; return s; }
        int mid = (s + e) / 2;
        int res;
        if (tree[2 * o] >= groupSize) res = assign(2 * o, s, mid, groupSize);
        else res = assign(2 * o + 1, mid + 1, e, groupSize);
        tree[o] = Math.max(tree[2 * o], tree[2 * o + 1]);
        return res;
    }
    
    public static void main(String[] args) {
        Problem34_SegmentTreeForHotelQueries sol = new Problem34_SegmentTreeForHotelQueries(new int[]{3, 2, 5, 1, 4});
        System.out.println(sol.assign(2)); // 0
        System.out.println(sol.assign(3)); // 2
        System.out.println(sol.assign(4)); // 4
        System.out.println(sol.assign(5)); // -1
    }
}
