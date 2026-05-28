import java.util.*;

/**
 * Problem: Employee Importance BFS (LeetCode 690)
 * Approach: BFS through employee hierarchy summing importance
 * Time: O(N), Space: O(N)
 * Production Analogy: Iterative impact assessment through org chart
 */
public class Problem29_EmployeeImportanceBFS {
    static class Employee { public int id, importance; public List<Integer> subordinates;
        Employee(int id, int imp, List<Integer> subs) { this.id=id; importance=imp; subordinates=subs; } }

    public int getImportance(List<Employee> employees, int id) {
        Map<Integer, Employee> map = new HashMap<>();
        for (Employee e : employees) map.put(e.id, e);
        Queue<Integer> q = new LinkedList<>();
        q.offer(id);
        int total = 0;
        while (!q.isEmpty()) {
            Employee e = map.get(q.poll());
            total += e.importance;
            for (int sub : e.subordinates) q.offer(sub);
        }
        return total;
    }

    public static void main(String[] args) {
        List<Employee> emps = Arrays.asList(
            new Employee(1, 5, Arrays.asList(2,3)),
            new Employee(2, 3, Arrays.asList()),
            new Employee(3, 3, Arrays.asList()));
        System.out.println(new Problem29_EmployeeImportanceBFS().getImportance(emps, 1)); // 11
    }
}
