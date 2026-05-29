import java.util.*;

/**
 * Problem: Find Champion II
 * In a tournament DAG, find the champion (node with in-degree 0, must be unique).
 *
 * Approach: Count in-degrees, champion exists iff exactly one node has in-degree 0
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V)
 *
 * Production Analogy: Finding the root authority in a delegation chain.
 */
public class Problem35_FindChampionII {

    public int findChampion(int n, int[][] edges) {
        int[] inDeg = new int[n];
        for (int[] e : edges) inDeg[e[1]]++;

        int champion = -1;
        for (int i = 0; i < n; i++) {
            if (inDeg[i] == 0) {
                if (champion != -1) return -1;
                champion = i;
            }
        }
        return champion;
    }

    public static void main(String[] args) {
        Problem35_FindChampionII solver = new Problem35_FindChampionII();
        System.out.println(solver.findChampion(3, new int[][]{{0,1},{1,2}})); // 0
        System.out.println(solver.findChampion(3, new int[][]{{0,2},{1,2}})); // -1
    }
}
