import java.util.*;

/**
 * Problem 33: Find the Town Judge (LeetCode 997)
 * 
 * Approach: Track in-degree and out-degree. Judge has in-degree n-1 and out-degree 0.
 * Time: O(V + E), Space: O(V)
 * 
 * Production Analogy: Finding the single authority service that all others trust but trusts no one.
 */
public class Problem33_FindTheTownJudge {
    
    public int findJudge(int n, int[][] trust) {
        int[] score = new int[n + 1]; // indegree - outdegree
        for (int[] t : trust) { score[t[0]]--; score[t[1]]++; }
        for (int i = 1; i <= n; i++) if (score[i] == n - 1) return i;
        return -1;
    }
    
    public static void main(String[] args) {
        Problem33_FindTheTownJudge sol = new Problem33_FindTheTownJudge();
        System.out.println(sol.findJudge(2, new int[][]{{1,2}})); // 2
        System.out.println(sol.findJudge(3, new int[][]{{1,3},{2,3}})); // 3
        System.out.println(sol.findJudge(3, new int[][]{{1,3},{2,3},{3,1}})); // -1
        System.out.println(sol.findJudge(1, new int[][]{})); // 1
    }
}
