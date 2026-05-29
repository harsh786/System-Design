import java.util.*;

public class Problem34_MergeSortStableRanking {
    // Stable ranking: assign ranks maintaining order of equal elements
    static int[] stableRank(int[] arr) {
        int n = arr.length;
        Integer[] indices = new Integer[n];
        for (int i = 0; i < n; i++) indices[i] = i;
        Arrays.sort(indices, (a, b) -> arr[a] != arr[b] ? arr[a] - arr[b] : a - b);
        int[] rank = new int[n];
        for (int i = 0; i < n; i++) rank[indices[i]] = i + 1;
        return rank;
    }
    
    public static void main(String[] args) {
        System.out.println(Arrays.toString(stableRank(new int[]{30, 10, 20, 10}))); // [4,1,3,2]
    }
}
