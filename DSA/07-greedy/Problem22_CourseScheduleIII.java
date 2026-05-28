/**
 * Problem 22: Course Schedule III (LeetCode 630)
 *
 * Greedy Choice: Sort by deadline. Take courses greedily; if over deadline, drop longest course taken.
 *
 * Time: O(n log n), Space: O(n)
 *
 * Production Analogy: Maximizing completed jobs with deadlines using preemptive scheduling.
 */
import java.util.*;
public class Problem22_CourseScheduleIII {
    
    public static int scheduleCourse(int[][] courses) {
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
        System.out.println(scheduleCourse(new int[][]{{100,200},{200,1300},{1000,1250},{2000,3200}})); // 3
        System.out.println(scheduleCourse(new int[][]{{1,2}}));        // 1
        System.out.println(scheduleCourse(new int[][]{{3,2},{4,3}}));  // 0
    }
}
