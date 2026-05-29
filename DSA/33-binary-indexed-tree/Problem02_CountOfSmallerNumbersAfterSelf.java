import java.util.*;

public class Problem02_CountOfSmallerNumbersAfterSelf {
    int[] bit;

    void update(int i, int n) {
        for (; i <= n; i += i & (-i)) bit[i]++;
    }

    int query(int i) {
        int s = 0;
        for (; i > 0; i -= i & (-i)) s += bit[i];
        return s;
    }

    public List<Integer> countSmaller(int[] nums) {
        int[] sorted = nums.clone();
        Arrays.sort(sorted);
        Map<Integer, Integer> ranks = new HashMap<>();
        int rank = 0;
        for (int v : sorted) if (!ranks.containsKey(v)) ranks.put(v, ++rank);
        int n = ranks.size();
        bit = new int[n + 1];
        Integer[] res = new Integer[nums.length];
        for (int i = nums.length - 1; i >= 0; i--) {
            int r = ranks.get(nums[i]);
            res[i] = query(r - 1);
            update(r, n);
        }
        return Arrays.asList(res);
    }

    public static void main(String[] args) {
        Problem02_CountOfSmallerNumbersAfterSelf sol = new Problem02_CountOfSmallerNumbersAfterSelf();
        System.out.println(sol.countSmaller(new int[]{5, 2, 6, 1})); // [2,1,1,0]
    }
}
