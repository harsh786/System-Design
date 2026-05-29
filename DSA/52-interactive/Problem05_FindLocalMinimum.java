import java.util.*;

public class Problem05_FindLocalMinimum {
    static int[] arr = {9, 6, 3, 14, 5, 7, 4};
    
    static int query(int i) { return arr[i]; }
    
    static int findLocalMin(int n) {
        int lo = 0, hi = n - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (query(mid) > query(mid + 1)) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }
    
    public static void main(String[] args) {
        int idx = findLocalMin(arr.length);
        System.out.println("Local min at index " + idx + " value=" + arr[idx]);
    }
}
