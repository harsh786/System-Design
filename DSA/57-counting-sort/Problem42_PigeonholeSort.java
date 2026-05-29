import java.util.*;

public class Problem42_PigeonholeSort {
    public static void pigeonholeSort(int[] arr) {
        int min = Integer.MAX_VALUE, max = Integer.MIN_VALUE;
        for (int n : arr) { min = Math.min(min, n); max = Math.max(max, n); }
        int range = max - min + 1;
        List<Integer>[] holes = new List[range];
        for (int i = 0; i < range; i++) holes[i] = new ArrayList<>();
        for (int n : arr) holes[n - min].add(n);
        int idx = 0;
        for (List<Integer> h : holes) for (int n : h) arr[idx++] = n;
    }

    public static void main(String[] args) {
        int[] arr = {8, 3, 2, 7, 4, 6, 8};
        pigeonholeSort(arr);
        System.out.println(Arrays.toString(arr));
    }
}
