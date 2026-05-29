import java.util.*;

public class Problem43_LexicographicalNumbers {
    public List<Integer> lexicalOrder(int n) {
        List<Integer> result = new ArrayList<>();
        for (int i = 1; i <= 9; i++) dfs(i, n, result);
        return result;
    }
    private void dfs(int cur, int n, List<Integer> result) {
        if (cur > n) return;
        result.add(cur);
        for (int i = 0; i <= 9; i++) dfs(cur*10+i, n, result);
    }
    public static void main(String[] args) { System.out.println(new Problem43_LexicographicalNumbers().lexicalOrder(13)); }
}
