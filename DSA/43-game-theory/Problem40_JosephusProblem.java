import java.util.*;

public class Problem40_JosephusProblem {
    // Josephus Problem: n people, every k-th eliminated. Find survivor.
    
    // Iterative O(n)
    public int josephus(int n, int k) {
        int pos = 0;
        for (int i = 2; i <= n; i++) pos = (pos + k) % i;
        return pos + 1;
    }
    
    // Recursive
    public int josephusRecursive(int n, int k) {
        if (n == 1) return 1;
        return (josephusRecursive(n - 1, k) + k - 1) % n + 1;
    }
    
    // Find elimination order
    public List<Integer> eliminationOrder(int n, int k) {
        List<Integer> circle = new ArrayList<>();
        for (int i = 1; i <= n; i++) circle.add(i);
        List<Integer> order = new ArrayList<>();
        int idx = 0;
        while (!circle.isEmpty()) {
            idx = (idx + k - 1) % circle.size();
            order.add(circle.remove(idx));
            if (!circle.isEmpty() && idx == circle.size()) idx = 0;
        }
        return order;
    }
    
    public static void main(String[] args) {
        Problem40_JosephusProblem sol = new Problem40_JosephusProblem();
        System.out.println(sol.josephus(7, 3));           // 4
        System.out.println(sol.josephusRecursive(7, 3));  // 4
        System.out.println(sol.eliminationOrder(7, 3));   // [3,6,2,7,5,1,4]
    }
}
