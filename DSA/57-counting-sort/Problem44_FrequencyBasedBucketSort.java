import java.util.*;

public class Problem44_FrequencyBasedBucketSort {
    // Sort elements by frequency, most frequent first
    public static List<Integer> sortByFrequency(int[] nums) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int n : nums) freq.merge(n, 1, Integer::sum);
        List<Integer>[] buckets = new List[nums.length + 1];
        for (var e : freq.entrySet()) {
            if (buckets[e.getValue()] == null) buckets[e.getValue()] = new ArrayList<>();
            buckets[e.getValue()].add(e.getKey());
        }
        List<Integer> result = new ArrayList<>();
        for (int i = buckets.length - 1; i >= 0; i--)
            if (buckets[i] != null) for (int v : buckets[i]) for (int j = 0; j < i; j++) result.add(v);
        return result;
    }

    public static void main(String[] args) {
        System.out.println(sortByFrequency(new int[]{1,1,1,2,2,3}));
    }
}
