import java.util.*;

public class Problem41_Combinations {
    public static List<List<Integer>> combine(int n, int k) {
        List<List<Integer>> res = new ArrayList<>();
        backtrack(res, new ArrayList<>(), 1, n, k);
        return res;
    }
    static void backtrack(List<List<Integer>> res, List<Integer> cur, int start, int n, int k) {
        if (cur.size() == k) { res.add(new ArrayList<>(cur)); return; }
        for (int i = start; i <= n - (k - cur.size()) + 1; i++) {
            cur.add(i); backtrack(res, cur, i + 1, n, k); cur.remove(cur.size() - 1);
        }
    }
    public static void main(String[] args) {
        System.out.println(combine(4, 2));
    }
}
