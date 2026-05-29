import java.util.*;

public class Problem17_RandomFlipMatrix {
    // Virtual mapping of remaining indices using HashMap
    Map<Integer, Integer> map;
    int rows, cols, total;
    Random rand;

    public Problem17_RandomFlipMatrix(int m, int n) {
        rows = m; cols = n; total = m * n;
        map = new HashMap<>(); rand = new Random();
    }

    public int[] flip() {
        int r = rand.nextInt(total--);
        int val = map.getOrDefault(r, r);
        map.put(r, map.getOrDefault(total, total));
        return new int[]{val / cols, val % cols};
    }

    public void reset() { map.clear(); total = rows * cols; }

    public static void main(String[] args) {
        Problem17_RandomFlipMatrix sol = new Problem17_RandomFlipMatrix(3, 3);
        for (int i = 0; i < 5; i++) System.out.println(Arrays.toString(sol.flip()));
        sol.reset();
        System.out.println("After reset: " + Arrays.toString(sol.flip()));
    }
}
