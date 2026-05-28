import java.util.*;

/**
 * Problem 48: Merge K Sorted Arrays
 * 
 * Approach: Min-heap with one element from each array. Extract min, advance that array's pointer.
 * 
 * Time Complexity: O(N log K) where N = total elements, K = number of arrays
 * Space Complexity: O(K)
 * 
 * Production Analogy: Merging sorted result sets from multiple database shards
 * into a globally sorted result for pagination.
 */
public class Problem48_MergeKSortedArrays {
    
    public List<Integer> mergeKArrays(int[][] arrays) {
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[0] - b[0]);
        for (int i = 0; i < arrays.length; i++) {
            if (arrays[i].length > 0) pq.offer(new int[]{arrays[i][0], i, 0});
        }
        
        List<Integer> result = new ArrayList<>();
        while (!pq.isEmpty()) {
            int[] curr = pq.poll();
            result.add(curr[0]);
            int arrIdx = curr[1], elemIdx = curr[2];
            if (elemIdx + 1 < arrays[arrIdx].length) {
                pq.offer(new int[]{arrays[arrIdx][elemIdx + 1], arrIdx, elemIdx + 1});
            }
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem48_MergeKSortedArrays sol = new Problem48_MergeKSortedArrays();
        int[][] arrays = {{1, 4, 7}, {2, 5, 8}, {3, 6, 9}};
        System.out.println(sol.mergeKArrays(arrays)); // [1,2,3,4,5,6,7,8,9]
        
        int[][] arrays2 = {{1, 3, 5}, {2, 4, 6}, {0, 7}};
        System.out.println(sol.mergeKArrays(arrays2)); // [0,1,2,3,4,5,6,7]
    }
}
