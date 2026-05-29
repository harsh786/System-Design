import java.util.*;

public class Problem42_SlidingWindowDistinctCount {
    // Sliding Window Distinct Count: Count distinct elements in last k elements.
    
    Map<Integer, Integer> freq = new HashMap<>();
    Queue<Integer> window = new LinkedList<>();
    int k;
    
    public Problem42_SlidingWindowDistinctCount() { this.k = 5; }
    
    public void init(int k) { this.k = k; }
    
    public int add(int val) {
        window.offer(val);
        freq.merge(val, 1, Integer::sum);
        if (window.size() > k) {
            int removed = window.poll();
            freq.merge(removed, -1, Integer::sum);
            if (freq.get(removed) == 0) freq.remove(removed);
        }
        return freq.size();
    }
    
    public static void main(String[] args) {
        Problem42_SlidingWindowDistinctCount sol = new Problem42_SlidingWindowDistinctCount();
        sol.init(4);
        int[] stream = {1,2,1,3,4,2,5};
        for (int v : stream) System.out.println("Add " + v + " -> distinct: " + sol.add(v));
    }
}
