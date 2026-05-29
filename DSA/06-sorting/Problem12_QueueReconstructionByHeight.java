import java.util.*;

/**
 * Problem 12: Queue Reconstruction by Height
 * 
 * People described by [h, k] where h=height, k=number of people in front >= h.
 * Reconstruct the queue.
 * 
 * Approach: Sort by height desc, then k asc. Insert each person at index k.
 * Time Complexity: O(n²) due to list insertions
 * Space Complexity: O(n)
 * 
 * Production Analogy: Priority-based task scheduling where both priority level and 
 * position constraints must be satisfied simultaneously.
 */
public class Problem12_QueueReconstructionByHeight {
    
    public int[][] reconstructQueue(int[][] people) {
        // Tallest first; same height, fewer people in front first
        Arrays.sort(people, (a, b) -> a[0] == b[0] ? a[1] - b[1] : b[0] - a[0]);
        
        List<int[]> result = new ArrayList<>();
        for (int[] p : people) {
            result.add(p[1], p);
        }
        return result.toArray(new int[people.length][]);
    }
    
    public static void main(String[] args) {
        Problem12_QueueReconstructionByHeight sol = new Problem12_QueueReconstructionByHeight();
        
        int[][] t1 = {{7,0},{4,4},{7,1},{5,0},{6,1},{5,2}};
        System.out.println("Test 1: " + Arrays.deepToString(sol.reconstructQueue(t1)));
        // [[5,0],[7,0],[5,2],[6,1],[4,4],[7,1]]
        
        int[][] t2 = {{6,0},{5,0},{4,0},{3,2},{2,2},{1,4}};
        System.out.println("Test 2: " + Arrays.deepToString(sol.reconstructQueue(t2)));
    }
}
