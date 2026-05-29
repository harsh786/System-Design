import java.util.*;

public class Problem03_SkylineProblem {
    public List<List<Integer>> getSkyline(int[][] buildings) {
        List<int[]> events = new ArrayList<>();
        for (int[] b : buildings) { events.add(new int[]{b[0], -b[2]}); events.add(new int[]{b[1], b[2]}); }
        events.sort((a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
        TreeMap<Integer, Integer> heights = new TreeMap<>(Collections.reverseOrder());
        heights.put(0, 1);
        int prevMax = 0;
        List<List<Integer>> res = new ArrayList<>();
        for (int[] e : events) {
            if (e[1] < 0) heights.merge(-e[1], 1, Integer::sum);
            else { heights.merge(e[1], -1, Integer::sum); if (heights.get(e[1]) == 0) heights.remove(e[1]); }
            int curMax = heights.firstKey();
            if (curMax != prevMax) { res.add(Arrays.asList(e[0], curMax)); prevMax = curMax; }
        }
        return res;
    }

    public static void main(String[] args) {
        Problem03_SkylineProblem sol = new Problem03_SkylineProblem();
        System.out.println(sol.getSkyline(new int[][]{{2,9,10},{3,7,15},{5,12,12},{15,20,10},{19,24,8}}));
    }
}
