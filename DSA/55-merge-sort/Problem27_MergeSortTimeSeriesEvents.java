import java.util.*;

public class Problem27_MergeSortTimeSeriesEvents {
    static int[][] mergeEvents(int[][] e1, int[][] e2) {
        int[][] result = new int[e1.length + e2.length][2];
        int i = 0, j = 0, k = 0;
        while (i < e1.length && j < e2.length)
            result[k++] = e1[i][0] <= e2[j][0] ? e1[i++] : e2[j++];
        while (i < e1.length) result[k++] = e1[i++];
        while (j < e2.length) result[k++] = e2[j++];
        return Arrays.copyOf(result, k);
    }
    
    public static void main(String[] args) {
        int[][] e1 = {{1,10},{3,30},{5,50}};
        int[][] e2 = {{2,20},{4,40},{6,60}};
        int[][] merged = mergeEvents(e1, e2);
        for (int[] e : merged) System.out.println(Arrays.toString(e));
    }
}
