import java.util.*;

public class Problem44_AirportGateAssignment {
    public int minGates(int[][] flights) {
        TreeMap<Integer, Integer> sweep = new TreeMap<>();
        for (int[] f : flights) { sweep.merge(f[0], 1, Integer::sum); sweep.merge(f[1], -1, Integer::sum); }
        int max = 0, cur = 0;
        for (int v : sweep.values()) { cur += v; max = Math.max(max, cur); }
        return max;
    }

    public static void main(String[] args) {
        Problem44_AirportGateAssignment sol = new Problem44_AirportGateAssignment();
        System.out.println(sol.minGates(new int[][]{{900,910},{940,1200},{950,1120},{1100,1130},{1500,1900}})); // 3
    }
}
