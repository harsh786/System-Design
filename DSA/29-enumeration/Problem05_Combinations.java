import java.util.*;

public class Problem05_Combinations {
    public List<List<Integer>> combine(int n, int k) {
        List<List<Integer>> result = new ArrayList<>();
        backtrack(result, new ArrayList<>(), 1, n, k);
        return result;
    }

    private void backtrack(List<List<Integer>> result, List<Integer> temp, int start, int n, int k) {
        if (temp.size() == k) { result.add(new ArrayList<>(temp)); return; }
        for (int i = start; i <= n-(k-temp.size())+1; i++) { temp.add(i); backtrack(result,temp,i+1,n,k); temp.remove(temp.size()-1); }
    }

    public static void main(String[] args) { System.out.println(new Problem05_Combinations().combine(4,2)); }
}
