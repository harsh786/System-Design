import java.util.*;

public class Problem10_CoordinateCompressionWithFenwick {
    int[] bit;
    void update(int i, int n) { for (; i <= n; i += i & (-i)) bit[i]++; }
    int query(int i) { int s = 0; for (; i > 0; i -= i & (-i)) s += bit[i]; return s; }

    public int[] countSmallerWithCompression(int[] nums) {
        int[] sorted = Arrays.stream(nums).distinct().sorted().toArray();
        Map<Integer, Integer> comp = new HashMap<>();
        for (int i = 0; i < sorted.length; i++) comp.put(sorted[i], i + 1);
        int n = sorted.length;
        bit = new int[n + 1];
        int[] res = new int[nums.length];
        for (int i = nums.length - 1; i >= 0; i--) {
            int r = comp.get(nums[i]);
            res[i] = query(r - 1);
            update(r, n);
        }
        return res;
    }

    public static void main(String[] args) {
        int[] res = new Problem10_CoordinateCompressionWithFenwick()
            .countSmallerWithCompression(new int[]{5, 2, 6, 1});
        System.out.println(Arrays.toString(res)); // [2, 1, 1, 0]
    }
}
