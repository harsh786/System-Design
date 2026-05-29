import java.util.*;

public class Problem26_CountingSortForTopKFrequent {
    public static List<Integer> topK(int[] nums, int k) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int n : nums) freq.merge(n, 1, Integer::sum);
        List<Integer>[] buckets = new List[nums.length + 1];
        for (var e : freq.entrySet()) {
            if (buckets[e.getValue()] == null) buckets[e.getValue()] = new ArrayList<>();
            buckets[e.getValue()].add(e.getKey());
        }
        List<Integer> result = new ArrayList<>();
        for (int i = buckets.length - 1; i >= 0 && result.size() < k; i--)
            if (buckets[i] != null) result.addAll(buckets[i]);
        return result.subList(0, k);
    }

    public static void main(String[] args) {
        System.out.println(topK(new int[]{1,1,1,2,2,3}, 2));
    }
}
