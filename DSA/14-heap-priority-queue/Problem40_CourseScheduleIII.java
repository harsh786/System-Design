import java.util.*;

/**
 * Problem 40: Course Schedule III (LeetCode 630)
 * 
 * Approach: Sort by deadline. Greedily take courses; if over deadline, drop the longest
 * course taken so far (max-heap).
 * 
 * Time Complexity: O(N log N)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Sprint planning - maximizing number of tasks completed within
 * their deadlines by swapping out longer tasks when needed.
 */
public class Problem40_CourseScheduleIII {
    
    public int scheduleCourse(int[][] courses) {
        Arrays.sort(courses, (a, b) -> a[1] - b[1]);
        PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
        int time = 0;
        
        for (int[] c : courses) {
            time += c[0];
            maxHeap.offer(c[0]);
            if (time > c[1]) {
                time -= maxHeap.poll();
            }
        }
        return maxHeap.size();
    }
    
    public static void main(String[] args) {
        Problem40_CourseScheduleIII sol = new Problem40_CourseScheduleIII();
        System.out.println(sol.scheduleCourse(new int[][]{{100,200},{200,1300},{1000,1250},{2000,3200}})); // 3
        System.out.println(sol.scheduleCourse(new int[][]{{1,2}})); // 1
        System.out.println(sol.scheduleCourse(new int[][]{{3,2},{4,3}})); // 0
    }
}
