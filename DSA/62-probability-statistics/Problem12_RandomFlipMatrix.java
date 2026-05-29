import java.util.*;

public class Problem12_RandomFlipMatrix {
    private Map<Integer, Integer> map = new HashMap<>();
    private int rows, cols, total;
    private Random rand = new Random();

    public Problem12_RandomFlipMatrix(int m, int n) { rows = m; cols = n; total = m * n; }

    public int[] flip() {
        int r = rand.nextInt(total--);
        int x = map.getOrDefault(r, r);
        map.put(r, map.getOrDefault(total, total));
        return new int[]{x / cols, x % cols};
    }

    public void reset() { map.clear(); total = rows * cols; }

    public static void main(String[] args) {
        Problem12_RandomFlipMatrix sol = new Problem12_RandomFlipMatrix(3, 3);
        for (int i = 0; i < 5; i++) System.out.println(Arrays.toString(sol.flip()));
    }
}
