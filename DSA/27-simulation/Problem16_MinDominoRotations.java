/**
 * Problem: Minimum Domino Rotations For Equal Row (LeetCode 1007)
 * Approach: Check if tops[0] or bottoms[0] can fill entire row
 * Complexity: O(n) time, O(1) space
 * Production Analogy: Minimizing configuration changes for uniform deployment
 */
public class Problem16_MinDominoRotations {
    public int minDominoRotations(int[] tops, int[] bottoms) {
        int res = check(tops[0], tops, bottoms);
        if (res != -1) return res;
        return check(bottoms[0], tops, bottoms);
    }
    private int check(int target, int[] A, int[] B) {
        int rotA = 0, rotB = 0;
        for (int i = 0; i < A.length; i++) {
            if (A[i] != target && B[i] != target) return -1;
            if (A[i] != target) rotA++;
            if (B[i] != target) rotB++;
        }
        return Math.min(rotA, rotB);
    }
    public static void main(String[] args) {
        System.out.println(new Problem16_MinDominoRotations().minDominoRotations(
            new int[]{2,1,2,4,2,2}, new int[]{5,2,6,2,3,2})); // 2
    }
}
