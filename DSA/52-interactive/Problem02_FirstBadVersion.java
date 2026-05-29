import java.util.*;

public class Problem02_FirstBadVersion {
    static int firstBad = 4;
    
    static boolean isBadVersion(int version) { return version >= firstBad; }
    
    static int firstBadVersion(int n) {
        int lo = 1, hi = n;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (isBadVersion(mid)) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }
    
    public static void main(String[] args) {
        System.out.println("First bad version: " + firstBadVersion(10)); // 4
    }
}
