import java.util.*;

public class Problem23_CountingSortMemoryTradeoff {
    // Compare memory: counting sort vs comparison sort
    public static void main(String[] args) {
        int n = 1000000, range = 100;
        Random rand = new Random();
        int[] arr = new int[n];
        for (int i = 0; i < n; i++) arr[i] = rand.nextInt(range);

        // Counting sort: O(n + k) time, O(k) extra space
        long start = System.nanoTime();
        int[] count = new int[range];
        for (int v : arr) count[v]++;
        int idx = 0;
        for (int i = 0; i < range; i++) while (count[i]-- > 0) arr[idx++] = i;
        long countTime = System.nanoTime() - start;

        // Reset
        for (int i = 0; i < n; i++) arr[i] = rand.nextInt(range);
        start = System.nanoTime();
        Arrays.sort(arr);
        long compTime = System.nanoTime() - start;

        System.out.printf("Counting sort: %dms (O(%d) extra space)%n", countTime/1000000, range);
        System.out.printf("Arrays.sort:   %dms (O(log n) extra space)%n", compTime/1000000);
    }
}
