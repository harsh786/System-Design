import java.util.*;

/**
 * Problem 49: Pascal's Triangle
 * Generate first numRows of Pascal's triangle.
 * 
 * Production Analogy: Like computing cascading dependency weights in a DAG -
 * each node's weight is sum of parent weights (combinatorial fan-out).
 * 
 * O(n^2) time, O(n^2) space
 */
public class Problem49_PascalsTriangle {

    public static List<List<Integer>> generate(int numRows) {
        List<List<Integer>> result = new ArrayList<>();
        for (int i = 0; i < numRows; i++) {
            List<Integer> row = new ArrayList<>();
            for (int j = 0; j <= i; j++)
                row.add((j == 0 || j == i) ? 1 : result.get(i-1).get(j-1) + result.get(i-1).get(j));
            result.add(row);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(generate(5)); // [[1],[1,1],[1,2,1],[1,3,3,1],[1,4,6,4,1]]
        System.out.println(generate(1)); // [[1]]
    }
}
