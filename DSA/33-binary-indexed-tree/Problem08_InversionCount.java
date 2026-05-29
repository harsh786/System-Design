import java.util.*;

public class Problem08_InversionCount {
    int[] bit;
    void update(int i, int n) { for (; i <= n; i += i & (-i)) bit[i]++; }
    int query(int i) { int s = 0; for (; i > 0; i -= i & (-i)) s += bit[i]; return s; }

    public long countInversions(int[] arr) {
        int[] sorted = arr.clone();
        Arrays.sort(sorted);
        Map<Integer, Integer> rank = new HashMap<>();
        int r = 0;
        for (int v : sorted) if (!rank.containsKey(v)) rank.put(v, ++r);
        int n = rank.size();
        bit = new int[n + 1];
        long inv = 0;
        for (int i = arr.length - 1; i >= 0; i--) {
            int rk = rank.get(arr[i]);
            inv += query(rk - 1);
            update(rk, n);
        }
        return inv;
    }

    public static void main(String[] args) {
        System.out.println(new Problem08_InversionCount().countInversions(new int[]{2, 4, 1, 3, 5})); // 3
    }
}
