import java.util.*;

public class Problem33_ApproximateMedian {
    /* Approximate median using sampling */
    public int approximateMedian(int[] arr) {
        Random rand = new Random();
        int sampleSize = Math.min(21, arr.length);
        int[] sample = new int[sampleSize];
        for (int i = 0; i < sampleSize; i++) sample[i] = arr[rand.nextInt(arr.length)];
        Arrays.sort(sample);
        return sample[sampleSize / 2];
    }

    public static void main(String[] args) {
        Problem33_ApproximateMedian sol = new Problem33_ApproximateMedian();
        int[] arr = new int[1000];
        Random r = new Random(42);
        for (int i = 0; i < 1000; i++) arr[i] = r.nextInt(10000);
        System.out.println("Approximate median: " + sol.approximateMedian(arr));
    }
}
