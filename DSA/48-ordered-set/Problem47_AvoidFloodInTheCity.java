import java.util.*;

public class Problem47_AvoidFloodInTheCity {
    // LC 1488: Avoid flood - dry lakes strategically
    public static int[] avoidFlood(int[] rains) {
        int[] ans = new int[rains.length];
        Map<Integer, Integer> full = new HashMap<>(); // lake -> day it was filled
        TreeSet<Integer> dryDays = new TreeSet<>();
        Arrays.fill(ans, -1);
        for (int i = 0; i < rains.length; i++) {
            if (rains[i] == 0) {
                dryDays.add(i);
                ans[i] = 1; // placeholder
            } else {
                int lake = rains[i];
                if (full.containsKey(lake)) {
                    Integer dryDay = dryDays.ceiling(full.get(lake));
                    if (dryDay == null) return new int[0];
                    ans[dryDay] = lake;
                    dryDays.remove(dryDay);
                }
                full.put(lake, i);
            }
        }
        return ans;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(avoidFlood(new int[]{1,2,0,0,2,1})));
        // [-1,-1,2,1,-1,-1]
    }
}
