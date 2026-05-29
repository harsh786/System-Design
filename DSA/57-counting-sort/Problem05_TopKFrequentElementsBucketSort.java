import java.util.*;

public class Problem05_TopKFrequentElementsBucketSort {
    public static int[] topKFrequent(int[] nums, int k) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int n : nums) freq.merge(n, 1, Integer::sum);
        List<Integer>[] buckets = new List[nums.length + 1];
        for (var e : freq.entrySet()) {
            if (buckets[e.getValue()] == null) buckets[e.getValue()] = new ArrayList<>();
            buckets[e.getValue()].add(e.getKey());
        }
        int[] result = new int[k];
        int idx = 0;
        for (int i = buckets.length - 1; i >= 0 && idx < k; i--)
            if (buckets[i] != null) for (int v : buckets[i]) { result[idx++] = v; if (idx == k) break; }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(topKFrequent(new int[]{1,1,1,2,2,3}, 2)));
    }
}
