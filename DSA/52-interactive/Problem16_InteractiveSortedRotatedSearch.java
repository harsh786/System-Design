import java.util.*;

public class Problem16_InteractiveSortedRotatedSearch {
    static int[] arr = {15, 18, 2, 3, 6, 12};
    static int query(int i) { return arr[i]; }
    
    static int search(int n, int target) {
        int lo = 0, hi = n - 1;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            int m = query(mid);
            if (m == target) return mid;
            if (query(lo) <= m) {
                if (target >= query(lo) && target < m) hi = mid - 1;
                else lo = mid + 1;
            } else {
                if (target > m && target <= query(hi)) lo = mid + 1;
                else hi = mid - 1;
            }
        }
        return -1;
    }
    
    public static void main(String[] args) {
        System.out.println("Search 3: " + search(arr.length, 3)); // 3
    }
}
