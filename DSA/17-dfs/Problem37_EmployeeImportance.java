import java.util.*;

/**
 * Problem: Employee Importance (LeetCode 690)
 * Approach: DFS through employee hierarchy summing importance values
 * Time: O(N), Space: O(N)
 * Production Analogy: Calculating total cost/impact of a team in org hierarchy
 */
public class Problem37_EmployeeImportance {
    static class Employee { public int id, importance; public List<Integer> subordinates;
        Employee(int id, int imp, List<Integer> subs) { this.id=id; importance=imp; subordinates=subs; } }

    public int getImportance(List<Employee> employees, int id) {
        Map<Integer, Employee> map = new HashMap<>();
        for (Employee e : employees) map.put(e.id, e);
        return dfs(map, id);
    }

    private int dfs(Map<Integer, Employee> map, int id) {
        Employee e = map.get(id);
        int total = e.importance;
        for (int sub : e.subordinates) total += dfs(map, sub);
        return total;
    }

    public static void main(String[] args) {
        List<Employee> emps = Arrays.asList(
            new Employee(1, 5, Arrays.asList(2,3)),
            new Employee(2, 3, Arrays.asList()),
            new Employee(3, 3, Arrays.asList()));
        System.out.println(new Problem37_EmployeeImportance().getImportance(emps, 1)); // 11
    }
}
