/**
 * Problem 27: Search in a Sorted Array of Unknown Size
 * 
 * Given an interface with get(index), array is sorted, find target.
 * Out of bounds returns Integer.MAX_VALUE.
 * 
 * Approach: Exponential search to find bounds, then binary search.
 * 
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Searching a paginated API where total count is unknown —
 * double page offset until overshoot, then binary search.
 */
public class Problem27_SearchInSortedArrayOfUnknownSize {

    // Simulated "infinite" array reader
    static int[] data;
    static int get(int index) {
        if (index >= data.length) return Integer.MAX_VALUE;
        return data[index];
    }

    public static int search(int target) {
        // Find boundary using exponential expansion
        int lo = 0, hi = 1;
        while (get(hi) < target) hi *= 2;
        
        // Standard binary search
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            int val = get(mid);
            if (val == target) return mid;
            else if (val < target) lo = mid + 1;
            else hi = mid - 1;
        }
        return -1;
    }

    public static void main(String[] args) {
        data = new int[]{-1,0,3,5,9,12};
        System.out.println(search(9));  // 4
        System.out.println(search(2));  // -1

        data = new int[]{1,3,5,7,9,11,13,15,17,19,21};
        System.out.println(search(15)); // 7
        System.out.println(search(20)); // -1
    }
}
