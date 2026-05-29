import java.util.*;

public class Problem45_BandwidthAllocation {
    public int peakBandwidth(int[][] sessions) {
        TreeMap<Integer, Integer> sweep = new TreeMap<>();
        for (int[] s : sessions) { sweep.merge(s[0], s[2], Integer::sum); sweep.merge(s[1], -s[2], Integer::sum); }
        int max = 0, cur = 0;
        for (int v : sweep.values()) { cur += v; max = Math.max(max, cur); }
        return max;
    }

    public static void main(String[] args) {
        Problem45_BandwidthAllocation sol = new Problem45_BandwidthAllocation();
        // [start, end, bandwidth]
        System.out.println(sol.peakBandwidth(new int[][]{{0,10,100},{5,15,200},{10,20,150}})); // 350
    }
}
