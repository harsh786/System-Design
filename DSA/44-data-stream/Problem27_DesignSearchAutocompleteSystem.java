import java.util.*;

public class Problem27_DesignSearchAutocompleteSystem {
    // 642. Design Search Autocomplete System.
    
    Map<String, Integer> freq = new HashMap<>();
    StringBuilder current = new StringBuilder();
    
    public void init(String[] sentences, int[] times) {
        for (int i = 0; i < sentences.length; i++) freq.put(sentences[i], times[i]);
    }
    
    public List<String> input(char c) {
        if (c == '#') { freq.merge(current.toString(), 1, Integer::sum); current = new StringBuilder(); return new ArrayList<>(); }
        current.append(c);
        String prefix = current.toString();
        PriorityQueue<String> pq = new PriorityQueue<>((a,b) -> {
            int diff = freq.get(a) - freq.get(b);
            return diff != 0 ? diff : b.compareTo(a);
        });
        for (var e : freq.entrySet()) {
            if (e.getKey().startsWith(prefix)) {
                pq.offer(e.getKey());
                if (pq.size() > 3) pq.poll();
            }
        }
        List<String> res = new ArrayList<>();
        while (!pq.isEmpty()) res.add(0, pq.poll());
        return res;
    }
    
    public static void main(String[] args) {
        Problem27_DesignSearchAutocompleteSystem sol = new Problem27_DesignSearchAutocompleteSystem();
        sol.init(new String[]{"i love you","island","iroman","i love leetcode"}, new int[]{5,3,2,2});
        System.out.println(sol.input('i')); // [i love you, island, i love leetcode]
        System.out.println(sol.input(' ')); // [i love you, i love leetcode]
    }
}
