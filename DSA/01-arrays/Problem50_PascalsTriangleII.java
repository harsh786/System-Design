import java.util.*;

/**
 * Problem 50: Pascal's Triangle II
 * Return the kth row (0-indexed) of Pascal's triangle using O(k) space.
 * 
 * Production Analogy: Like computing a single layer of aggregation in a reduce step
 * without materializing all prior layers - space-efficient rolling computation.
 * 
 * O(k^2) time, O(k) space - update row in place from right to left
 */
public class Problem50_PascalsTriangleII {

    public static List<Integer> getRow(int rowIndex) {
        List<Integer> row = new ArrayList<>(Collections.nCopies(rowIndex + 1, 1));
        for (int i = 2; i <= rowIndex; i++)
            for (int j = i - 1; j >= 1; j--)
                row.set(j, row.get(j) + row.get(j - 1));
        return row;
    }

    public static void main(String[] args) {
        System.out.println(getRow(3)); // [1,3,3,1]
        System.out.println(getRow(0)); // [1]
        System.out.println(getRow(1)); // [1,1]
        System.out.println(getRow(4)); // [1,4,6,4,1]
    }
}
