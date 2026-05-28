/**
 * Problem 8: Queue Reconstruction by Height (LeetCode 406)
 *
 * Greedy Choice: Sort by height desc, then k asc. Insert each person at index k.
 * Taller people placed first won't be affected by shorter people inserted later.
 *
 * Time: O(n^2), Space: O(n)
 *
 * Production Analogy: Priority queue reconstruction in distributed task scheduling.
 */
import java.util.*;
public class Problem08_QueueReconstructionByHeight {
    
    public static int[][] reconstructQueue(int[][] people) {
        Arrays.sort(people, (a, b) -> a[0] != b[0] ? b[0] - a[0] : a[1] - b[1]);
        List<int[]> result = new ArrayList<>();
        for (int[] p : people) result.add(p[1], p);
        return result.toArray(new int[0][]);
    }
    
    public static void main(String[] args) {
        int[][] res = reconstructQueue(new int[][]{{7,0},{4,4},{7,1},{5,0},{6,1},{5,2}});
        for (int[] p : res) System.out.print(Arrays.toString(p) + " ");
        // [5,0] [7,0] [5,2] [6,1] [4,4] [7,1]
        System.out.println();
    }
}
