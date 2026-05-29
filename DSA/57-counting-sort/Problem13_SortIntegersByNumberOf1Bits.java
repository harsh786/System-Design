import java.util.*;

public class Problem13_SortIntegersByNumberOf1Bits {
    public static int[] sortByBits(int[] arr) {
        Integer[] a = new Integer[arr.length];
        for (int i = 0; i < arr.length; i++) a[i] = arr[i];
        Arrays.sort(a, (x, y) -> {
            int bx = Integer.bitCount(x), by = Integer.bitCount(y);
            return bx != by ? bx - by : x - y;
        });
        for (int i = 0; i < arr.length; i++) arr[i] = a[i];
        return arr;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(sortByBits(new int[]{0,1,2,3,4,5,6,7,8})));
    }
}
