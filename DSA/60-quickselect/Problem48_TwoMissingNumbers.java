import java.util.*;

public class Problem48_TwoMissingNumbers {
    /* Find two missing numbers from 1..n+2 using XOR and partitioning */
    public int[] findTwoMissing(int[] arr, int n) {
        int xorAll = 0;
        for (int i = 1; i <= n; i++) xorAll ^= i;
        for (int x : arr) xorAll ^= x;
        // xorAll = missing1 ^ missing2
        int setBit = xorAll & (-xorAll);
        int group1 = 0, group2 = 0;
        for (int i = 1; i <= n; i++) {
            if ((i & setBit) != 0) group1 ^= i; else group2 ^= i;
        }
        for (int x : arr) {
            if ((x & setBit) != 0) group1 ^= x; else group2 ^= x;
        }
        return new int[]{group1, group2};
    }

    public static void main(String[] args) {
        Problem48_TwoMissingNumbers sol = new Problem48_TwoMissingNumbers();
        // Array contains 1..7 except 3 and 5
        System.out.println(Arrays.toString(sol.findTwoMissing(new int[]{1, 2, 4, 6, 7}, 7)));
    }
}
