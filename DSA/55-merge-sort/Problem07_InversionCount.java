public class Problem07_InversionCount {
    static long countInversions(int[] arr) {
        return mergeSort(arr, 0, arr.length - 1);
    }
    
    static long mergeSort(int[] a, int lo, int hi) {
        if (lo >= hi) return 0;
        int mid = (lo + hi) / 2;
        long c = mergeSort(a, lo, mid) + mergeSort(a, mid + 1, hi);
        int[] tmp = new int[hi - lo + 1];
        int i = lo, j = mid + 1, k = 0;
        while (i <= mid && j <= hi) {
            if (a[i] <= a[j]) tmp[k++] = a[i++];
            else { c += mid - i + 1; tmp[k++] = a[j++]; }
        }
        while (i <= mid) tmp[k++] = a[i++];
        while (j <= hi) tmp[k++] = a[j++];
        System.arraycopy(tmp, 0, a, lo, tmp.length);
        return c;
    }
    
    public static void main(String[] args) {
        System.out.println(countInversions(new int[]{5, 4, 3, 2, 1})); // 10
    }
}
