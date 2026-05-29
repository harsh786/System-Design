import java.util.*;

public class Problem42_CombinationSumII {
    public static List<List<Integer>> combinationSum2(int[] candidates, int target) {
        Arrays.sort(candidates);
        List<List<Integer>> res = new ArrayList<>();
        backtrack(res, new ArrayList<>(), candidates, target, 0);
        return res;
    }
    static void backtrack(List<List<Integer>> res, List<Integer> cur, int[] cands, int remain, int start) {
        if (remain == 0) { res.add(new ArrayList<>(cur)); return; }
        for (int i = start; i < cands.length; i++) {
            if (cands[i] > remain) break;
            if (i > start && cands[i] == cands[i - 1]) continue;
            cur.add(cands[i]); backtrack(res, cur, cands, remain - cands[i], i + 1); cur.remove(cur.size() - 1);
        }
    }
    public static void main(String[] args) {
        System.out.println(combinationSum2(new int[]{10,1,2,7,6,1,5}, 8));
    }
}
