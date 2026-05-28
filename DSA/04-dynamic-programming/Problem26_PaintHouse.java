/**
 * Problem 26: Paint House
 * 
 * n houses, 3 colors, no two adjacent houses same color. Minimize cost.
 * costs[i][j] = cost of painting house i with color j.
 * 
 * State: dp[i][c] = min cost painting houses 0..i with house i color c
 * Time: O(n), Space: O(1)
 */
public class Problem26_PaintHouse {

    public static int minCost(int[][] costs) {
        if (costs.length == 0) return 0;
        int r = costs[0][0], g = costs[0][1], b = costs[0][2];
        for (int i = 1; i < costs.length; i++) {
            int nr = costs[i][0] + Math.min(g, b);
            int ng = costs[i][1] + Math.min(r, b);
            int nb = costs[i][2] + Math.min(r, g);
            r = nr; g = ng; b = nb;
        }
        return Math.min(r, Math.min(g, b));
    }

    public static void main(String[] args) {
        System.out.println("=== Paint House ===");
        System.out.println(minCost(new int[][]{{17,2,17},{16,16,5},{14,3,19}})); // 10
        System.out.println(minCost(new int[][]{{7,6,2}})); // 2
    }
}
