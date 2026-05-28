import java.util.*;

/**
 * Problem 13: Smallest Range Covering Elements from K Lists (LeetCode 632)
 * 
 * Approach: Min-heap with one element from each list. Track max. The range is
 * [heap.peek(), currentMax]. Advance the min element's list pointer.
 * 
 * Time Complexity: O(N log K) where N = total elements
 * Space Complexity: O(K)
 * 
 * Production Analogy: Finding the smallest time window that captures at least one
 * event from each microservice for correlated log analysis.
 */
public class Problem13_SmallestRangeCoveringKLists {
    
    public int[] smallestRange(List<List<Integer>> nums) {
        PriorityQueue<int[]> minHeap = new PriorityQueue<>((a, b) -> a[0] - b[0]);
        int max = Integer.MIN_VALUE;
        
        for (int i = 0; i < nums.size(); i++) {
            int val = nums.get(i).get(0);
            minHeap.offer(new int[]{val, i, 0});
            max = Math.max(max, val);
        }
        
        int[] result = {minHeap.peek()[0], max};
        
        while (true) {
            int[] curr = minHeap.poll();
            int listIdx = curr[1], elemIdx = curr[2];
            if (elemIdx + 1 >= nums.get(listIdx).size()) break;
            
            int nextVal = nums.get(listIdx).get(elemIdx + 1);
            minHeap.offer(new int[]{nextVal, listIdx, elemIdx + 1});
            max = Math.max(max, nextVal);
            
            if (max - minHeap.peek()[0] < result[1] - result[0]) {
                result = new int[]{minHeap.peek()[0], max};
            }
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem13_SmallestRangeCoveringKLists sol = new Problem13_SmallestRangeCoveringKLists();
        List<List<Integer>> nums = Arrays.asList(
            Arrays.asList(4, 10, 15, 24, 26),
            Arrays.asList(0, 9, 12, 20),
            Arrays.asList(5, 18, 22, 30)
        );
        System.out.println(Arrays.toString(sol.smallestRange(nums))); // [20, 24]
    }
}
