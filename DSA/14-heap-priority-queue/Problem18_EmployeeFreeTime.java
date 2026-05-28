import java.util.*;

/**
 * Problem 18: Employee Free Time (LeetCode 759)
 * 
 * Approach: Merge all intervals using min-heap sorted by start time,
 * find gaps between merged intervals.
 * 
 * Time Complexity: O(N log K) where N = total intervals, K = employees
 * Space Complexity: O(K)
 * 
 * Production Analogy: Finding common maintenance windows across multiple services
 * for coordinated deployment scheduling.
 */
public class Problem18_EmployeeFreeTime {
    
    public List<int[]> employeeFreeTime(List<List<int[]>> schedule) {
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[0] - b[0]);
        for (List<int[]> emp : schedule)
            for (int[] interval : emp) pq.offer(interval);
        
        List<int[]> result = new ArrayList<>();
        int[] prev = pq.poll();
        
        while (!pq.isEmpty()) {
            int[] curr = pq.poll();
            if (curr[0] > prev[1]) {
                result.add(new int[]{prev[1], curr[0]});
                prev = curr;
            } else {
                prev[1] = Math.max(prev[1], curr[1]);
            }
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem18_EmployeeFreeTime sol = new Problem18_EmployeeFreeTime();
        List<List<int[]>> schedule = Arrays.asList(
            Arrays.asList(new int[]{1,2}, new int[]{5,6}),
            Arrays.asList(new int[]{1,3}),
            Arrays.asList(new int[]{4,10})
        );
        List<int[]> res = sol.employeeFreeTime(schedule);
        for (int[] r : res) System.out.println(Arrays.toString(r)); // [3,4]
    }
}
