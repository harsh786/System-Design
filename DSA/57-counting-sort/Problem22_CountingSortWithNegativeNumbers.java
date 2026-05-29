import java.util.*;

public class Problem22_CountingSortWithNegativeNumbers {
    public static int[] countingSort(int[] arr) {
        int min = Integer.MAX_VALUE, max = Integer.MIN_VALUE;
        for (int n : arr) { min = Math.min(min, n); max = Math.max(max, n); }
        int range = max - min + 1;
        int[] count = new int[range];
        for (int n : arr) count[n - min]++;
        int idx = 0;
        for (int i = 0; i < range; i++) while (count[i]-- > 0) arr[idx++] = i + min;
        return arr;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(countingSort(new int[]{-5, 3, -1, 0, 2, -3, 4})));
    }
}
