import java.util.*;

public class Problem40_BucketSortImplementation {
    public static void bucketSort(float[] arr) {
        int n = arr.length;
        List<Float>[] buckets = new List[n];
        for (int i = 0; i < n; i++) buckets[i] = new ArrayList<>();
        for (float v : arr) buckets[(int)(v * n)].add(v);
        for (List<Float> b : buckets) Collections.sort(b);
        int idx = 0;
        for (List<Float> b : buckets) for (float v : b) arr[idx++] = v;
    }

    public static void main(String[] args) {
        float[] arr = {0.78f, 0.17f, 0.39f, 0.26f, 0.72f, 0.94f, 0.21f, 0.12f, 0.23f, 0.68f};
        bucketSort(arr);
        System.out.println(Arrays.toString(arr));
    }
}
