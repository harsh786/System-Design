import java.util.*;

public class Problem36_BridgeAndTorch {
    // N people cross bridge (2 at a time, need torch). Minimize total time.
    static int minCrossTime(int[] times) {
        Arrays.sort(times);
        int n = times.length, total = 0;
        while (n > 3) {
            // Strategy 1: fastest escorts each. Strategy 2: two slowest go together
            int s1 = times[0] + times[n-1] + times[0] + times[n-2];
            int s2 = times[1] + times[0] + times[n-1] + times[1];
            total += Math.min(s1, s2);
            n -= 2;
        }
        if (n == 3) total += times[0] + times[1] + times[2];
        else if (n == 2) total += times[1];
        else total += times[0];
        return total;
    }
    
    public static void main(String[] args) {
        System.out.println(minCrossTime(new int[]{1, 2, 5, 10})); // 17
    }
}
