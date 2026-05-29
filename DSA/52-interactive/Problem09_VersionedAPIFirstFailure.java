import java.util.*;

public class Problem09_VersionedAPIFirstFailure {
    static int failVersion = 15;
    
    static boolean testVersion(int v) { return v >= failVersion; }
    
    static int findFirstFailure(int totalVersions) {
        int lo = 1, hi = totalVersions;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (testVersion(mid)) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }
    
    public static void main(String[] args) {
        System.out.println("First failing version: " + findFirstFailure(30)); // 15
    }
}
