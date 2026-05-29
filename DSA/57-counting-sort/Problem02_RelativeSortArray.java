import java.util.*;

public class Problem02_RelativeSortArray {
    public static int[] relativeSortArray(int[] arr1, int[] arr2) {
        int[] count = new int[1001];
        for (int n : arr1) count[n]++;
        int idx = 0;
        for (int n : arr2) while (count[n]-- > 0) arr1[idx++] = n;
        for (int i = 0; i < 1001; i++) while (count[i]-- > 0) arr1[idx++] = i;
        return arr1;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(relativeSortArray(
            new int[]{2,3,1,3,2,4,6,7,9,2,19}, new int[]{2,1,4,3,9,6})));
    }
}
