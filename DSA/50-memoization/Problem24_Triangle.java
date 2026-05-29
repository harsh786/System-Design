import java.util.*;

public class Problem24_Triangle {
    private Integer[][] memo;

    public int minimumTotal(List<List<Integer>> triangle) {
        memo = new Integer[triangle.size()][triangle.size()];
        return helper(triangle, 0, 0);
    }

    private int helper(List<List<Integer>> tri, int row, int col) {
        if (row == tri.size()) return 0;
        if (memo[row][col] != null) return memo[row][col];
        memo[row][col] = tri.get(row).get(col) + Math.min(helper(tri, row+1, col), helper(tri, row+1, col+1));
        return memo[row][col];
    }

    public static void main(String[] args) {
        Problem24_Triangle sol = new Problem24_Triangle();
        List<List<Integer>> tri = Arrays.asList(Arrays.asList(2),Arrays.asList(3,4),Arrays.asList(6,5,7),Arrays.asList(4,1,8,3));
        System.out.println("Triangle min path: " + sol.minimumTotal(tri)); // 11
    }
}
