import java.util.*;

/**
 * Problem 19: Brick Wall
 * Find where to draw a vertical line that crosses the fewest bricks.
 *
 * Approach: For each row, compute prefix sums (edge positions). Count edges at each position.
 * The line should go through the position with maximum edges. Answer = rows - maxEdges.
 *
 * Time Complexity: O(n) where n = total bricks
 * Space Complexity: O(width)
 *
 * Production Analogy: Like finding optimal partition points in a distributed system
 * where you want to split data with minimum cross-partition references.
 */
public class Problem19_BrickWall {
    public int leastBricks(List<List<Integer>> wall) {
        Map<Integer, Integer> edgeCount = new HashMap<>();
        for (List<Integer> row : wall) {
            int sum = 0;
            for (int i = 0; i < row.size() - 1; i++) { // skip last edge (wall boundary)
                sum += row.get(i);
                edgeCount.merge(sum, 1, Integer::sum);
            }
        }
        int maxEdges = 0;
        for (int count : edgeCount.values()) maxEdges = Math.max(maxEdges, count);
        return wall.size() - maxEdges;
    }

    public static void main(String[] args) {
        Problem19_BrickWall sol = new Problem19_BrickWall();
        List<List<Integer>> wall = Arrays.asList(
            Arrays.asList(1,2,2,1), Arrays.asList(3,1,2),
            Arrays.asList(1,3,2), Arrays.asList(2,4),
            Arrays.asList(3,1,2), Arrays.asList(1,3,1,1)
        );
        System.out.println(sol.leastBricks(wall)); // 2
        System.out.println(sol.leastBricks(Arrays.asList(Arrays.asList(1), Arrays.asList(1)))); // 2
    }
}
