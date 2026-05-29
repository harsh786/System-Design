import java.util.*;

public class Problem39_HeavyHittersMisraGries {
    // Misra-Gries Algorithm: Find heavy hitters (elements with freq > n/k).
    
    Map<Integer, Integer> counters;
    int k;
    
    public Problem39_HeavyHittersMisraGries() { init(3); }
    
    public void init(int k) { this.k = k; counters = new HashMap<>(); }
    
    public void add(int item) {
        if (counters.containsKey(item)) {
            counters.put(item, counters.get(item) + 1);
        } else if (counters.size() < k - 1) {
            counters.put(item, 1);
        } else {
            // Decrement all counters
            Iterator<Map.Entry<Integer, Integer>> it = counters.entrySet().iterator();
            while (it.hasNext()) {
                Map.Entry<Integer, Integer> e = it.next();
                e.setValue(e.getValue() - 1);
                if (e.getValue() == 0) it.remove();
            }
        }
    }
    
    public Set<Integer> getCandidates() { return counters.keySet(); }
    
    public static void main(String[] args) {
        Problem39_HeavyHittersMisraGries sol = new Problem39_HeavyHittersMisraGries();
        sol.init(3); // find elements with freq > n/3
        int[] stream = {1,2,1,1,3,2,1,2,1,3,1,2};
        for (int v : stream) sol.add(v);
        System.out.println("Heavy hitter candidates: " + sol.getCandidates()); // {1, 2}
    }
}
