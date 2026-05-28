import java.util.*;

/**
 * Problem 47: Top K Frequent Words (LeetCode 692)
 * 
 * Approach: Count frequencies, use min-heap of size K with custom comparator
 * (by freq ascending, then lexicographic descending).
 * 
 * Time Complexity: O(N log K)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Search engine autocomplete - finding top-K most searched
 * terms with alphabetical tiebreaking.
 */
public class Problem47_TopKFrequentWords {
    
    public List<String> topKFrequent(String[] words, int k) {
        Map<String, Integer> freq = new HashMap<>();
        for (String w : words) freq.merge(w, 1, Integer::sum);
        
        PriorityQueue<String> pq = new PriorityQueue<>((a, b) -> {
            int fa = freq.get(a), fb = freq.get(b);
            return fa != fb ? fa - fb : b.compareTo(a);
        });
        
        for (String w : freq.keySet()) {
            pq.offer(w);
            if (pq.size() > k) pq.poll();
        }
        
        List<String> result = new ArrayList<>();
        while (!pq.isEmpty()) result.add(pq.poll());
        Collections.reverse(result);
        return result;
    }
    
    public static void main(String[] args) {
        Problem47_TopKFrequentWords sol = new Problem47_TopKFrequentWords();
        System.out.println(sol.topKFrequent(new String[]{"i","love","leetcode","i","love","coding"}, 2)); // [i, love]
        System.out.println(sol.topKFrequent(new String[]{"the","day","is","sunny","the","the","the","sunny","is","is"}, 4)); // [the, is, sunny, day]
    }
}
