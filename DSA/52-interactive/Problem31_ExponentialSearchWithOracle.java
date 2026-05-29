import java.util.*;

public class Problem31_ExponentialSearchWithOracle {
    static int[] arr = {2,3,5,7,11,13,17,19,23,29,31,37,41,43,47};
    static int query(int i) { return i < arr.length ? arr[i] : Integer.MAX_VALUE; }
    
    static int expSearch(int target) {
        if (query(0) == target) return 0;
        int bound = 1;
        while (query(bound) < target) bound *= 2;
        int lo = bound / 2, hi = bound;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            int v = query(mid);
            if (v == target) return mid;
            else if (v < target) lo = mid + 1;
            else hi = mid - 1;
        }
        return -1;
    }
    
    public static void main(String[] args) {
        System.out.println("Search 23: " + expSearch(23)); // 8
    }
}
