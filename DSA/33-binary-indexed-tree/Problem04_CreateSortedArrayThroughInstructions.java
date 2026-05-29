import java.util.*;

public class Problem04_CreateSortedArrayThroughInstructions {
    int[] bit;
    void update(int i, int n) { for (; i <= n; i += i & (-i)) bit[i]++; }
    int query(int i) { int s = 0; for (; i > 0; i -= i & (-i)) s += bit[i]; return s; }

    public int createSortedArray(int[] instructions) {
        int max = 100001;
        bit = new int[max + 1];
        long cost = 0, MOD = 1_000_000_007;
        for (int i = 0; i < instructions.length; i++) {
            int less = query(instructions[i] - 1);
            int greater = i - query(instructions[i]);
            cost = (cost + Math.min(less, greater)) % MOD;
            update(instructions[i], max);
        }
        return (int) cost;
    }

    public static void main(String[] args) {
        System.out.println(new Problem04_CreateSortedArrayThroughInstructions()
            .createSortedArray(new int[]{1,5,6,2})); // 1
    }
}
