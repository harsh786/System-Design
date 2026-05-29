import java.util.*;

public class Problem33_MergeSortCountGreaterAfter {
    static int[] count;
    
    static int[] countGreater(int[] nums) {
        int n = nums.length; count = new int[n];
        int[][] indexed = new int[n][2];
        for (int i = 0; i < n; i++) indexed[i] = new int[]{nums[i], i};
        ms(indexed, 0, n - 1);
        return count;
    }
    
    static void ms(int[][] a, int lo, int hi) {
        if (lo >= hi) return;
        int mid = (lo + hi) / 2; ms(a, lo, mid); ms(a, mid + 1, hi);
        int[][] tmp = new int[hi - lo + 1][]; int i = lo, j = mid + 1, k = 0;
        while (i <= mid && j <= hi) {
            if (a[i][0] > a[j][0]) { count[a[i][1]] += hi - j + 1; tmp[k++] = a[i++]; }
            else tmp[k++] = a[j++];
        }
        while (i <= mid) tmp[k++] = a[i++]; while (j <= hi) tmp[k++] = a[j++];
        System.arraycopy(tmp, 0, a, lo, tmp.length);
    }
    
    public static void main(String[] args) {
        System.out.println(Arrays.toString(countGreater(new int[]{5, 2, 6, 1}))); // [2,1,1,0]
    }
}
