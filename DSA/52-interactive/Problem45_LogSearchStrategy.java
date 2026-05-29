import java.util.*;

public class Problem45_LogSearchStrategy {
    // Search sorted log entries by timestamp using binary search
    static long[] timestamps = {100,200,300,400,500,600,700,800,900,1000};
    static String[] logs = {"init","start","connect","auth","query","process","respond","log","close","shutdown"};
    
    static long getTimestamp(int i) { return timestamps[i]; }
    
    static int findFirstAfter(int n, long targetTime) {
        int lo = 0, hi = n - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (getTimestamp(mid) >= targetTime) hi = mid;
            else lo = mid + 1;
        }
        return getTimestamp(lo) >= targetTime ? lo : -1;
    }
    
    public static void main(String[] args) {
        int idx = findFirstAfter(10, 450);
        System.out.println("First log after 450: " + logs[idx] + " at " + timestamps[idx]);
    }
}
