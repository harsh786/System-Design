/**
 * Problem: Max Value of Equation (LC 1499)
 * yi+yj+|xi-xj| = (yj-xj) + (yi+xi). Monotonic deque on (yj-xj) with window |xi-xj|<=k.
 * Time: O(n) | Space: O(n)
 * Production Analogy: Optimal pairing of servers by distance with proximity constraint.
 */
import java.util.*;

public class Problem06_MaxValueOfEquation {
    public static int findMaxValueOfEquation(int[][] points, int k) {
        Deque<int[]> deque = new ArrayDeque<>(); // [yj - xj, xj]
        int ans = Integer.MIN_VALUE;
        for (int[] p : points) {
            while (!deque.isEmpty() && p[0] - deque.peekFirst()[1] > k) deque.pollFirst();
            if (!deque.isEmpty()) ans = Math.max(ans, p[1] + p[0] + deque.peekFirst()[0]);
            while (!deque.isEmpty() && deque.peekLast()[0] <= p[1] - p[0]) deque.pollLast();
            deque.offerLast(new int[]{p[1] - p[0], p[0]});
        }
        return ans;
    }

    public static void main(String[] args) {
        System.out.println(findMaxValueOfEquation(new int[][]{{1,3},{2,0},{5,10},{6,-10}}, 1)); // 4
        System.out.println(findMaxValueOfEquation(new int[][]{{0,0},{3,0},{9,2}}, 3)); // 3
    }
}
