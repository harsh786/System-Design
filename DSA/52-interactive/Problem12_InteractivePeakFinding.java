import java.util.*;

public class Problem12_InteractivePeakFinding {
    static int[] arr = {1, 3, 5, 7, 6, 4, 2};
    static int query(int i) { return arr[i]; }
    
    static int findPeak(int n) {
        int lo = 0, hi = n - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (query(mid) < query(mid + 1)) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }
    
    public static void main(String[] args) {
        int idx = findPeak(arr.length);
        System.out.println("Peak at index " + idx + " value=" + arr[idx]);
    }
}
