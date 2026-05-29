import java.util.*;

public class Problem24_SeparateEvenOdd {
    public void separate(int[] arr) {
        int lo = 0, hi = arr.length - 1;
        while (lo < hi) {
            while (lo < hi && arr[lo] % 2 == 0) lo++;
            while (lo < hi && arr[hi] % 2 == 1) hi--;
            if (lo < hi) { int t = arr[lo]; arr[lo] = arr[hi]; arr[hi] = t; lo++; hi--; }
        }
    }

    public static void main(String[] args) {
        Problem24_SeparateEvenOdd sol = new Problem24_SeparateEvenOdd();
        int[] arr = {12, 34, 45, 9, 8, 90, 3};
        sol.separate(arr);
        System.out.println(Arrays.toString(arr));
    }
}
