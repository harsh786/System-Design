import java.util.*;

public class Problem12_CarPooling {
    public boolean carPooling(int[][] trips, int capacity) {
        int[] diff = new int[1001];
        for (int[] t : trips) { diff[t[1]] += t[0]; diff[t[2]] -= t[0]; }
        int cur = 0;
        for (int d : diff) { cur += d; if (cur > capacity) return false; }
        return true;
    }

    public static void main(String[] args) {
        Problem12_CarPooling sol = new Problem12_CarPooling();
        System.out.println(sol.carPooling(new int[][]{{2,1,5},{3,3,7}}, 4)); // false
        System.out.println(sol.carPooling(new int[][]{{2,1,5},{3,5,7}}, 3)); // true
    }
}
