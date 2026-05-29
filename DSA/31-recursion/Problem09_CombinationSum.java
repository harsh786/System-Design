import java.util.*;

public class Problem09_CombinationSum {
    public static List<List<Integer>> combinationSum(int[] candidates, int target) {
        List<List<Integer>> res = new ArrayList<>();
        backtrack(res, new ArrayList<>(), candidates, target, 0);
        return res;
    }
    static void backtrack(List<List<Integer>> res, List<Integer> cur, int[] cands, int remain, int start) {
        if (remain == 0) { res.add(new ArrayList<>(cur)); return; }
        for (int i = start; i < cands.length; i++) {
            if (cands[i] > remain) continue;
            cur.add(cands[i]);
            backtrack(res, cur, cands, remain - cands[i], i);
            cur.remove(cur.size() - 1);
        }
    }
    public static void main(String[] args) {
        System.out.println(combinationSum(new int[]{2, 3, 6, 7}, 7));
    }
}
