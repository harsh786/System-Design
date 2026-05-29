import java.util.*;

public class Problem23_MinimumIntervalToIncludeEachQuery {
    // LC 1851: For each query, find smallest interval [l,r] containing it
    public static int[] minInterval(int[][] intervals, int[] queries) {
        Arrays.sort(intervals, (a, b) -> a[0] - b[0]);
        int[] sortedQ = queries.clone();
        Arrays.sort(sortedQ);
        Map<Integer, Integer> res = new HashMap<>();
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[0] - b[0]);
        int j = 0;
        for (int q : sortedQ) {
            while (j < intervals.length && intervals[j][0] <= q) {
                pq.offer(new int[]{intervals[j][1] - intervals[j][0] + 1, intervals[j][1]});
                j++;
            }
            while (!pq.isEmpty() && pq.peek()[1] < q) pq.poll();
            res.put(q, pq.isEmpty() ? -1 : pq.peek()[0]);
        }
        int[] ans = new int[queries.length];
        for (int i = 0; i < queries.length; i++) ans[i] = res.get(queries[i]);
        return ans;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(minInterval(
            new int[][]{{1,4},{2,4},{3,6},{4,4}}, new int[]{2,3,4,5})));
        // [3,3,1,4]
    }
}
