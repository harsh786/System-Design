import java.util.*;

public class Problem49_CombinationsWithRepetition {
    // Choose k items from n types with repetition allowed
    public List<List<Integer>> combineWithRepetition(int[] items, int k) {
        List<List<Integer>> result = new ArrayList<>();
        backtrack(result, new ArrayList<>(), items, k, 0);
        return result;
    }

    private void backtrack(List<List<Integer>> result, List<Integer> temp, int[] items, int k, int start) {
        if (temp.size() == k) { result.add(new ArrayList<>(temp)); return; }
        for (int i = start; i < items.length; i++) {
            temp.add(items[i]);
            backtrack(result, temp, items, k, i); // allow reuse
            temp.remove(temp.size() - 1);
        }
    }

    public static void main(String[] args) {
        System.out.println(new Problem49_CombinationsWithRepetition().combineWithRepetition(new int[]{1,2,3}, 2));
    }
}
