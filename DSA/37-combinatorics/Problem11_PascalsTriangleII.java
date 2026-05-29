import java.util.*;

public class Problem11_PascalsTriangleII {
    public List<Integer> getRow(int rowIndex) {
        List<Integer> row = new ArrayList<>();
        row.add(1);
        for (int i = 1; i <= rowIndex; i++) {
            row.add((int)((long)row.get(i-1) * (rowIndex - i + 1) / i));
        }
        return row;
    }

    public static void main(String[] args) {
        System.out.println(new Problem11_PascalsTriangleII().getRow(4));
    }
}
