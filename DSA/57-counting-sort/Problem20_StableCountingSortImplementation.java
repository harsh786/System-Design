import java.util.*;

public class Problem20_StableCountingSortImplementation {
    // Classic stable counting sort
    public static int[] stableCountingSort(int[] arr, int maxVal) {
        int[] count = new int[maxVal + 1];
        for (int n : arr) count[n]++;
        // prefix sum for positions
        for (int i = 1; i <= maxVal; i++) count[i] += count[i-1];
        int[] output = new int[arr.length];
        for (int i = arr.length - 1; i >= 0; i--) {
            output[count[arr[i]] - 1] = arr[i];
            count[arr[i]]--;
        }
        return output;
    }

    public static void main(String[] args) {
        int[] arr = {4, 2, 2, 8, 3, 3, 1};
        System.out.println(Arrays.toString(stableCountingSort(arr, 8)));
    }
}
