import java.util.*;

public class Problem31_MergeSortDeduplicate {
    static int[] sortAndDedup(int[] arr) {
        Arrays.sort(arr);
        int j = 0;
        for (int i = 1; i < arr.length; i++) if (arr[i] != arr[j]) arr[++j] = arr[i];
        return Arrays.copyOf(arr, j + 1);
    }
    
    public static void main(String[] args) {
        System.out.println(Arrays.toString(sortAndDedup(new int[]{3,1,2,3,1,4,2,5})));
    }
}
