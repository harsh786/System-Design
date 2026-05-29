import java.util.*;

public class Problem31_EventCounterDifferenceArray {
    public int[] eventCount(int[][] events, int maxTime) {
        int[] diff = new int[maxTime + 2];
        for (int[] e : events) { diff[e[0]]++; diff[e[1] + 1]--; }
        int[] res = new int[maxTime + 1];
        res[0] = diff[0];
        for (int i = 1; i <= maxTime; i++) res[i] = res[i-1] + diff[i];
        return res;
    }

    public static void main(String[] args) {
        Problem31_EventCounterDifferenceArray sol = new Problem31_EventCounterDifferenceArray();
        System.out.println(Arrays.toString(sol.eventCount(new int[][]{{1,3},{2,5},{4,6}}, 7)));
    }
}
