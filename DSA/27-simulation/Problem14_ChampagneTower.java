/**
 * Problem: Champagne Tower (LeetCode 799)
 * Approach: Simulate overflow row by row
 * Complexity: O(row^2) time, O(row) space
 * Production Analogy: Cascading resource distribution in hierarchical systems
 */
public class Problem14_ChampagneTower {
    public double champagneTower(int poured, int query_row, int query_glass) {
        double[] row = new double[]{poured};
        for (int r = 0; r < query_row; r++) {
            double[] next = new double[r+2];
            for (int i = 0; i <= r; i++) {
                double overflow = Math.max(0, row[i]-1) / 2.0;
                next[i] += overflow;
                next[i+1] += overflow;
            }
            row = next;
        }
        return Math.min(1.0, row[query_glass]);
    }
    public static void main(String[] args) {
        System.out.println(new Problem14_ChampagneTower().champagneTower(2, 1, 1)); // 0.5
    }
}
