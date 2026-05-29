import java.util.*;

/**
 * Problem 36: Employee Free Time
 * 
 * Given schedules of all employees, find common free time intervals.
 * 
 * Approach: Flatten all intervals, sort by start, merge, find gaps.
 * Time Complexity: O(n log n) where n = total intervals
 * Space Complexity: O(n)
 * 
 * Production Analogy: Finding maintenance windows across all services in a microservice
 * architecture - when ALL services have downtime tolerance simultaneously.
 */
public class Problem36_EmployeeFreeTime {
    
    public List<int[]> employeeFreeTime(List<List<int[]>> schedule) {
        List<int[]> all = new ArrayList<>();
        for (List<int[]> emp : schedule) all.addAll(emp);
        
        all.sort((a, b) -> a[0] - b[0]);
        
        List<int[]> result = new ArrayList<>();
        int end = all.get(0)[1];
        
        for (int i = 1; i < all.size(); i++) {
            if (all.get(i)[0] > end) {
                result.add(new int[]{end, all.get(i)[0]});
            }
            end = Math.max(end, all.get(i)[1]);
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem36_EmployeeFreeTime sol = new Problem36_EmployeeFreeTime();
        
        // Employee 1: [[1,2],[5,6]], Employee 2: [[1,3]], Employee 3: [[4,10]]
        List<List<int[]>> schedule1 = Arrays.asList(
            Arrays.asList(new int[]{1,2}, new int[]{5,6}),
            Arrays.asList(new int[]{1,3}),
            Arrays.asList(new int[]{4,10})
        );
        List<int[]> r1 = sol.employeeFreeTime(schedule1);
        System.out.print("Test 1: ");
        for (int[] interval : r1) System.out.print(Arrays.toString(interval) + " ");
        System.out.println(); // [3,4]
        
        // Employee 1: [[1,3],[6,7]], Employee 2: [[2,4]], Employee 3: [[2,5],[9,12]]
        List<List<int[]>> schedule2 = Arrays.asList(
            Arrays.asList(new int[]{1,3}, new int[]{6,7}),
            Arrays.asList(new int[]{2,4}),
            Arrays.asList(new int[]{2,5}, new int[]{9,12})
        );
        List<int[]> r2 = sol.employeeFreeTime(schedule2);
        System.out.print("Test 2: ");
        for (int[] interval : r2) System.out.print(Arrays.toString(interval) + " ");
        System.out.println(); // [5,6] [7,9]
    }
}
