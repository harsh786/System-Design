import java.util.*;

public class Problem49_PeakConcurrentUsers {
    public int[] peakConcurrent(int[][] sessions) {
        TreeMap<Integer, Integer> sweep = new TreeMap<>();
        for (int[] s : sessions) { sweep.merge(s[0], 1, Integer::sum); sweep.merge(s[1], -1, Integer::sum); }
        int max = 0, cur = 0, peakTime = 0;
        for (Map.Entry<Integer, Integer> e : sweep.entrySet()) {
            cur += e.getValue();
            if (cur > max) { max = cur; peakTime = e.getKey(); }
        }
        return new int[]{max, peakTime};
    }

    public static void main(String[] args) {
        Problem49_PeakConcurrentUsers sol = new Problem49_PeakConcurrentUsers();
        System.out.println(Arrays.toString(sol.peakConcurrent(new int[][]{{0,5},{1,6},{2,7},{3,8},{4,9}})));
    }
}
