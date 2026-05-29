import java.util.*;

public class Problem43_DistributionSort {
    // Sort by distributing elements into buckets based on value range
    public static void distributionSort(int[] arr, int numBuckets) {
        if (arr.length == 0) return;
        int min = Integer.MAX_VALUE, max = Integer.MIN_VALUE;
        for (int n : arr) { min = Math.min(min, n); max = Math.max(max, n); }
        double range = (double)(max - min + 1) / numBuckets;
        List<Integer>[] buckets = new List[numBuckets];
        for (int i = 0; i < numBuckets; i++) buckets[i] = new ArrayList<>();
        for (int n : arr) {
            int idx = Math.min((int)((n - min) / range), numBuckets - 1);
            buckets[idx].add(n);
        }
        for (List<Integer> b : buckets) Collections.sort(b);
        int idx = 0;
        for (List<Integer> b : buckets) for (int n : b) arr[idx++] = n;
    }

    public static void main(String[] args) {
        int[] arr = {29, 25, 3, 49, 9, 37, 21, 43};
        distributionSort(arr, 4);
        System.out.println(Arrays.toString(arr));
    }
}
