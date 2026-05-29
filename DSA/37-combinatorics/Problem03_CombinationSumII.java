import java.util.*;

public class Problem03_CombinationSumII {
    public List<List<Integer>> combinationSum2(int[] candidates, int target) {
        List<List<Integer>> result = new ArrayList<>();
        Arrays.sort(candidates);
        backtrack(result, new ArrayList<>(), candidates, target, 0);
        return result;
    }

    private void backtrack(List<List<Integer>> result, List<Integer> temp, int[] candidates, int remain, int start) {
        if (remain == 0) { result.add(new ArrayList<>(temp)); return; }
        for (int i = start; i < candidates.length && candidates[i] <= remain; i++) {
            if (i > start && candidates[i] == candidates[i-1]) continue;
            temp.add(candidates[i]);
            backtrack(result, temp, candidates, remain - candidates[i], i + 1);
            temp.remove(temp.size() - 1);
        }
    }

    public static void main(String[] args) {
        System.out.println(new Problem03_CombinationSumII().combinationSum2(new int[]{10,1,2,7,6,1,5}, 8));
    }
}
