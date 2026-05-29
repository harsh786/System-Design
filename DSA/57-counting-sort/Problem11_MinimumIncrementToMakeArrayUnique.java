import java.util.*;

public class Problem11_MinimumIncrementToMakeArrayUnique {
    public static int minIncrementForUnique(int[] nums) {
        int[] count = new int[200001];
        for (int n : nums) count[n]++;
        int moves = 0;
        for (int i = 0; i < 200000; i++) {
            if (count[i] > 1) {
                int extra = count[i] - 1;
                count[i+1] += extra;
                moves += extra;
            }
        }
        return moves;
    }

    public static void main(String[] args) {
        System.out.println(minIncrementForUnique(new int[]{1,2,2})); // 1
        System.out.println(minIncrementForUnique(new int[]{3,2,1,2,1,7})); // 6
    }
}
