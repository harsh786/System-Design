import java.util.*;

public class Problem46_DatabaseLockCulpritSearch {
    // Find which of N transactions is causing a lock
    static int culprit = 3;
    static int n = 8;
    
    static boolean hasLock(Set<Integer> running) { return running.contains(culprit); }
    
    static int findCulprit() {
        int lo = 0, hi = n - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            Set<Integer> batch = new HashSet<>();
            for (int i = lo; i <= mid; i++) batch.add(i);
            if (hasLock(batch)) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }
    
    public static void main(String[] args) {
        System.out.println("Lock culprit transaction: " + findCulprit()); // 3
    }
}
