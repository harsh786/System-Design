import java.util.*;

/**
 * Problem: Course Schedule III
 * Maximum number of courses you can take given durations and deadlines.
 *
 * Approach: Greedy - sort by deadline, use max-heap to drop longest course when over deadline
 *
 * Time Complexity: O(n log n)
 * Space Complexity: O(n)
 *
 * Production Analogy: Maximizing tasks completed before SLA deadlines with limited resources.
 */
public class Problem18_CourseScheduleIII {

    public int scheduleCourse(int[][] courses) {
        Arrays.sort(courses, (a, b) -> a[1] - b[1]);
        PriorityQueue<Integer> pq = new PriorityQueue<>(Collections.reverseOrder());
        int time = 0;

        for (int[] c : courses) {
            time += c[0];
            pq.offer(c[0]);
            if (time > c[1]) time -= pq.poll();
        }
        return pq.size();
    }

    public static void main(String[] args) {
        Problem18_CourseScheduleIII solver = new Problem18_CourseScheduleIII();
        System.out.println(solver.scheduleCourse(new int[][]{{100,200},{200,1300},{1000,1250},{2000,3200}})); // 3
    }
}
