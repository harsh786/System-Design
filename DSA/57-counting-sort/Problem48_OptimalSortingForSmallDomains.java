import java.util.*;

public class Problem48_OptimalSortingForSmallDomains {
    // Comparison: when k << n, counting sort beats O(n log n)
    public static void main(String[] args) {
        int n = 10000000;
        int[] domains = {5, 50, 500, 5000};
        Random rand = new Random(42);

        for (int k : domains) {
            int[] arr = new int[n];
            for (int i = 0; i < n; i++) arr[i] = rand.nextInt(k);

            long start = System.nanoTime();
            int[] count = new int[k];
            for (int v : arr) count[v]++;
            int idx = 0;
            for (int i = 0; i < k; i++) while (count[i]-- > 0) arr[idx++] = i;
            long countingTime = System.nanoTime() - start;

            for (int i = 0; i < n; i++) arr[i] = rand.nextInt(k);
            start = System.nanoTime();
            Arrays.sort(arr);
            long compTime = System.nanoTime() - start;

            System.out.printf("k=%5d: counting=%4dms, Arrays.sort=%4dms%n",
                k, countingTime/1000000, compTime/1000000);
        }
    }
}
