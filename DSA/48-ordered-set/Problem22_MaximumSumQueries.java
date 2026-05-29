import java.util.*;

public class Problem22_MaximumSumQueries {
    // LC 2736: Given nums1, nums2, queries [xi, yi], find max(nums1[j]+nums2[j]) where nums1[j]>=xi and nums2[j]>=yi
    public static int[] maximumSumQueries(int[] nums1, int[] nums2, int[][] queries) {
        int n = nums1.length, q = queries.length;
        int[][] pairs = new int[n][2];
        for (int i = 0; i < n; i++) pairs[i] = new int[]{nums1[i], nums2[i]};
        Arrays.sort(pairs, (a, b) -> b[0] - a[0]);
        Integer[] qIdx = new Integer[q];
        for (int i = 0; i < q; i++) qIdx[i] = i;
        Arrays.sort(qIdx, (a, b) -> queries[b][0] - queries[a][0]);
        TreeMap<Integer, Integer> map = new TreeMap<>(); // y -> max sum (monotonic)
        int[] ans = new int[q];
        int j = 0;
        for (int i : qIdx) {
            while (j < n && pairs[j][0] >= queries[i][0]) {
                int y = pairs[j][1], s = pairs[j][0] + pairs[j][1];
                // maintain decreasing values for increasing keys
                Integer key = map.floorKey(y);
                if (key != null && map.get(key) >= s) { j++; continue; }
                map.put(y, s);
                // remove dominated entries
                Integer hi = map.higherKey(y);
                while (hi != null && map.get(hi) <= s) { map.remove(hi); hi = map.higherKey(y); }
                j++;
            }
            Integer key = map.ceilingKey(queries[i][1]);
            ans[i] = key == null ? -1 : map.get(key);
        }
        return ans;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(maximumSumQueries(
            new int[]{4,3,1,2}, new int[]{2,4,9,5}, new int[][]{{4,1},{1,3},{2,5}})));
        // [6,10,7]
    }
}
