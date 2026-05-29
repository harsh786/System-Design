import java.util.*;

public class Problem21_PascalsTriangle {
    public static List<List<Integer>> generate(int numRows) {
        List<List<Integer>> res = new ArrayList<>();
        if (numRows == 0) return res;
        res.add(Arrays.asList(1));
        for (int i = 1; i < numRows; i++) {
            List<Integer> row = new ArrayList<>(); row.add(1);
            List<Integer> prev = res.get(i - 1);
            for (int j = 1; j < i; j++) row.add(prev.get(j - 1) + prev.get(j));
            row.add(1); res.add(row);
        }
        return res;
    }
    // Recursive approach for single element
    public static int pascalVal(int row, int col) {
        if (col == 0 || col == row) return 1;
        return pascalVal(row - 1, col - 1) + pascalVal(row - 1, col);
    }
    public static void main(String[] args) {
        System.out.println(generate(5));
        System.out.println(pascalVal(4, 2)); // 6
    }
}
