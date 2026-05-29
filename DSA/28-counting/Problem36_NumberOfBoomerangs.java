/**
 * Problem: Number of Boomerangs (LeetCode 447)
 * Approach: For each point, count distances to all others, permutations of same distance
 * Complexity: O(n^2) time, O(n) space
 * Production Analogy: Proximity-based grouping in geospatial analytics
 */
import java.util.*;
public class Problem36_NumberOfBoomerangs {
    public int numberOfBoomerangs(int[][] points) {
        int count = 0;
        for (int[] p : points) {
            Map<Integer, Integer> distMap = new HashMap<>();
            for (int[] q : points) {
                int d = (p[0]-q[0])*(p[0]-q[0]) + (p[1]-q[1])*(p[1]-q[1]);
                distMap.merge(d, 1, Integer::sum);
            }
            for (int v : distMap.values()) count += v * (v-1);
        }
        return count;
    }
    public static void main(String[] args) {
        System.out.println(new Problem36_NumberOfBoomerangs().numberOfBoomerangs(
            new int[][]{{0,0},{1,0},{2,0}})); // 2
    }
}
