import java.util.*;

public class Problem34_RangeAddition {
    public int[] getModifiedArray(int length, int[][] updates) {
        int[] diff = new int[length];
        for (int[] u : updates) { diff[u[0]] += u[2]; if (u[1] + 1 < length) diff[u[1] + 1] -= u[2]; }
        for (int i = 1; i < length; i++) diff[i] += diff[i-1];
        return diff;
    }

    public static void main(String[] args) {
        Problem34_RangeAddition sol = new Problem34_RangeAddition();
        System.out.println(Arrays.toString(sol.getModifiedArray(5, new int[][]{{1,3,2},{2,4,3},{0,2,-2}})));
    }
}
