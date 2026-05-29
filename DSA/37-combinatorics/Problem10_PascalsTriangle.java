import java.util.*;

public class Problem10_PascalsTriangle {
    public List<List<Integer>> generate(int numRows) {
        List<List<Integer>> result = new ArrayList<>();
        for (int i = 0; i < numRows; i++) {
            List<Integer> row = new ArrayList<>();
            for (int j = 0; j <= i; j++) {
                row.add(j == 0 || j == i ? 1 : result.get(i-1).get(j-1) + result.get(i-1).get(j));
            }
            result.add(row);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(new Problem10_PascalsTriangle().generate(5));
    }
}
