import java.util.*;

public class Problem06_CombinationSum {
    public List<List<Integer>> combinationSum(int[] candidates, int target) {
        List<List<Integer>> result = new ArrayList<>();
        Arrays.sort(candidates);
        backtrack(result, new ArrayList<>(), candidates, target, 0);
        return result;
    }

    private void backtrack(List<List<Integer>> result, List<Integer> temp, int[] cand, int remain, int start) {
        if (remain == 0) { result.add(new ArrayList<>(temp)); return; }
        for (int i = start; i < cand.length && cand[i] <= remain; i++) { temp.add(cand[i]); backtrack(result,temp,cand,remain-cand[i],i); temp.remove(temp.size()-1); }
    }

    public static void main(String[] args) { System.out.println(new Problem06_CombinationSum().combinationSum(new int[]{2,3,6,7},7)); }
}
