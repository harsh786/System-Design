import java.util.*;

public class Problem47_SortWithKnownRange {
    // When range is known and small, counting sort is optimal
    public static int[] sortKnownRange(int[] arr, int min, int max) {
        int[] count = new int[max - min + 1];
        for (int n : arr) count[n - min]++;
        int idx = 0;
        for (int i = 0; i < count.length; i++) while (count[i]-- > 0) arr[idx++] = i + min;
        return arr;
    }

    public static void main(String[] args) {
        // HTTP status codes (known range 100-599)
        int[] codes = {200, 404, 200, 500, 301, 200, 404, 500, 301};
        System.out.println(Arrays.toString(sortKnownRange(codes, 100, 599)));
    }
}
