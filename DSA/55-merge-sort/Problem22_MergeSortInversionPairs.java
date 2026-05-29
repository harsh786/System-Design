import java.util.*;

public class Problem22_MergeSortInversionPairs {
    static List<int[]> inversions = new ArrayList<>();
    
    static void findInversions(int[] arr) {
        inversions.clear();
        int[] copy = arr.clone();
        mergeSort(copy, arr.clone(), 0, arr.length - 1);
    }
    
    static void mergeSort(int[] a, int[] orig, int lo, int hi) {
        if (lo >= hi) return;
        int mid = (lo + hi) / 2; mergeSort(a, orig, lo, mid); mergeSort(a, orig, mid + 1, hi);
        int[] tmp = new int[hi - lo + 1]; int i = lo, j = mid + 1, k = 0;
        while (i <= mid && j <= hi) {
            if (a[i] <= a[j]) tmp[k++] = a[i++];
            else { for (int x = i; x <= mid; x++) inversions.add(new int[]{a[x], a[j]}); tmp[k++] = a[j++]; }
        }
        while (i <= mid) tmp[k++] = a[i++]; while (j <= hi) tmp[k++] = a[j++];
        System.arraycopy(tmp, 0, a, lo, tmp.length);
    }
    
    public static void main(String[] args) {
        findInversions(new int[]{3, 1, 2});
        System.out.println("Inversions: " + inversions.size()); // 2: (3,1), (3,2)
    }
}
