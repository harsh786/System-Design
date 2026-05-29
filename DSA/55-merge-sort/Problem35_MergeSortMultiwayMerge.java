import java.util.*;

public class Problem35_MergeSortMultiwayMerge {
    // K-way merge using divide and conquer
    static int[] kWayMerge(List<int[]> lists) {
        return dc(lists, 0, lists.size() - 1);
    }
    
    static int[] dc(List<int[]> lists, int lo, int hi) {
        if (lo == hi) return lists.get(lo);
        if (lo + 1 == hi) return merge(lists.get(lo), lists.get(hi));
        int mid = (lo + hi) / 2;
        return merge(dc(lists, lo, mid), dc(lists, mid + 1, hi));
    }
    
    static int[] merge(int[] a, int[] b) {
        int[] r = new int[a.length + b.length]; int i = 0, j = 0, k = 0;
        while (i < a.length && j < b.length) r[k++] = a[i] <= b[j] ? a[i++] : b[j++];
        while (i < a.length) r[k++] = a[i++]; while (j < b.length) r[k++] = b[j++];
        return r;
    }
    
    public static void main(String[] args) {
        List<int[]> lists = Arrays.asList(new int[]{1,5,9}, new int[]{2,6}, new int[]{3,7,10}, new int[]{4,8});
        System.out.println(Arrays.toString(kWayMerge(lists)));
    }
}
