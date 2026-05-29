import java.util.*;

public class Problem16_ClosestRoom {
    // LC 1847: For each query [preferred, minSize], find closest room with size >= minSize
    public static int[] closestRoom(int[][] rooms, int[][] queries) {
        int n = queries.length;
        int[] ans = new int[n];
        Integer[] idx = new Integer[n];
        for (int i = 0; i < n; i++) idx[i] = i;
        Arrays.sort(idx, (a, b) -> queries[b][1] - queries[a][1]);
        Arrays.sort(rooms, (a, b) -> b[1] - a[1]);
        TreeSet<Integer> ids = new TreeSet<>();
        int j = 0;
        for (int i : idx) {
            while (j < rooms.length && rooms[j][1] >= queries[i][1]) {
                ids.add(rooms[j][0]);
                j++;
            }
            int pref = queries[i][0];
            Integer lo = ids.floor(pref), hi = ids.ceiling(pref);
            if (lo == null && hi == null) ans[i] = -1;
            else if (lo == null) ans[i] = hi;
            else if (hi == null) ans[i] = lo;
            else ans[i] = (pref - lo <= hi - pref) ? lo : hi;
        }
        return ans;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(closestRoom(
            new int[][]{{2,2},{1,2},{3,2}}, new int[][]{{3,1},{3,3},{5,2}})));
        // [3, -1, 3]
    }
}
