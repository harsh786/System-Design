import java.util.*;

public class Problem07_HeightChecker {
    public static int heightChecker(int[] heights) {
        int[] count = new int[101];
        for (int h : heights) count[h]++;
        int mismatch = 0, idx = 0;
        for (int i = 1; i <= 100; i++)
            while (count[i]-- > 0) { if (heights[idx] != i) mismatch++; idx++; }
        return mismatch;
    }

    public static void main(String[] args) {
        System.out.println(heightChecker(new int[]{1,1,4,2,1,3})); // 3
        System.out.println(heightChecker(new int[]{5,1,2,3,4})); // 5
    }
}
