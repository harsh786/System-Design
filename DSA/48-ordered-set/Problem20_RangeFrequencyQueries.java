import java.util.*;

public class Problem20_RangeFrequencyQueries {
    // LC 2080: Query frequency of value in subarray [left, right]
    Map<Integer, List<Integer>> indexMap;

    public Problem20_RangeFrequencyQueries(int[] arr) {
        indexMap = new HashMap<>();
        for (int i = 0; i < arr.length; i++) {
            indexMap.computeIfAbsent(arr[i], k -> new ArrayList<>()).add(i);
        }
    }

    public int query(int left, int right, int value) {
        List<Integer> indices = indexMap.get(value);
        if (indices == null) return 0;
        int lo = Collections.binarySearch(indices, left);
        if (lo < 0) lo = -lo - 1;
        int hi = Collections.binarySearch(indices, right);
        if (hi < 0) hi = -hi - 2;
        else hi = hi; // exact match
        return Math.max(0, hi - lo + 1);
    }

    public static void main(String[] args) {
        Problem20_RangeFrequencyQueries q = new Problem20_RangeFrequencyQueries(new int[]{12,33,4,56,22,2,34,33,22,12,34,56});
        System.out.println(q.query(1, 2, 4));  // 1
        System.out.println(q.query(0, 11, 33)); // 2
    }
}
