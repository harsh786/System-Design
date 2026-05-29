import java.util.*;

public class Problem41_RadixSortImplementation {
    public static void radixSort(int[] arr) {
        // Handle negatives: separate, sort positives, sort abs(negatives), reverse negatives
        List<Integer> neg = new ArrayList<>(), pos = new ArrayList<>();
        for (int n : arr) { if (n < 0) neg.add(-n); else pos.add(n); }
        int[] posArr = pos.stream().mapToInt(i->i).toArray();
        int[] negArr = neg.stream().mapToInt(i->i).toArray();
        radixSortPositive(posArr);
        radixSortPositive(negArr);
        int idx = 0;
        for (int i = negArr.length - 1; i >= 0; i--) arr[idx++] = -negArr[i];
        for (int n : posArr) arr[idx++] = n;
    }

    static void radixSortPositive(int[] arr) {
        if (arr.length == 0) return;
        int max = Arrays.stream(arr).max().orElse(0);
        for (int exp = 1; max / exp > 0; exp *= 10) {
            int[] output = new int[arr.length], count = new int[10];
            for (int n : arr) count[(n/exp)%10]++;
            for (int i = 1; i < 10; i++) count[i] += count[i-1];
            for (int i = arr.length-1; i >= 0; i--) { output[--count[(arr[i]/exp)%10]] = arr[i]; }
            System.arraycopy(output, 0, arr, 0, arr.length);
        }
    }

    public static void main(String[] args) {
        int[] arr = {170, -45, 75, -90, 802, 24, 2, -66};
        radixSort(arr);
        System.out.println(Arrays.toString(arr));
    }
}
