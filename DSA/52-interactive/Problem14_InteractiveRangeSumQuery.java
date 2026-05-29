import java.util.*;

public class Problem14_InteractiveRangeSumQuery {
    static int[] arr = {2, 4, 6, 8, 10, 12};
    static int querySum(int l, int r) {
        int s = 0; for (int i = l; i <= r; i++) s += arr[i]; return s;
    }
    
    // Find index where prefix sum first exceeds threshold using binary search
    static int findThresholdIndex(int n, int threshold) {
        int lo = 0, hi = n - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (querySum(0, mid) >= threshold) hi = mid;
            else lo = mid + 1;
        }
        return querySum(0, lo) >= threshold ? lo : -1;
    }
    
    public static void main(String[] args) {
        System.out.println("First prefix sum >= 12: index " + findThresholdIndex(6, 12)); // 2
    }
}
