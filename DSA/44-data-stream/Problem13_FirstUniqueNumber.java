import java.util.*;

public class Problem13_FirstUniqueNumber {
    // 1429. First Unique Number in a stream.
    
    Map<Integer, Integer> count = new LinkedHashMap<>();
    
    public void add(int val) {
        count.merge(val, 1, Integer::sum);
    }
    
    public int showFirstUnique() {
        for (var e : count.entrySet()) {
            if (e.getValue() == 1) return e.getKey();
        }
        return -1;
    }
    
    public static void main(String[] args) {
        Problem13_FirstUniqueNumber sol = new Problem13_FirstUniqueNumber();
        sol.add(2); sol.add(3); sol.add(5);
        System.out.println(sol.showFirstUnique()); // 2
        sol.add(2);
        System.out.println(sol.showFirstUnique()); // 3
        sol.add(3);
        System.out.println(sol.showFirstUnique()); // 5
    }
}
