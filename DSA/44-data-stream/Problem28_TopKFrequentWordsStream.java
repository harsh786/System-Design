import java.util.*;

public class Problem28_TopKFrequentWordsStream {
    // Top K Frequent Words from a stream.
    
    Map<String, Integer> freq = new HashMap<>();
    
    public void add(String word) { freq.merge(word, 1, Integer::sum); }
    
    public List<String> topK(int k) {
        PriorityQueue<String> pq = new PriorityQueue<>((a,b) -> {
            int diff = freq.get(a) - freq.get(b);
            return diff != 0 ? diff : b.compareTo(a);
        });
        for (String w : freq.keySet()) {
            pq.offer(w);
            if (pq.size() > k) pq.poll();
        }
        List<String> res = new ArrayList<>();
        while (!pq.isEmpty()) res.add(0, pq.poll());
        return res;
    }
    
    public static void main(String[] args) {
        Problem28_TopKFrequentWordsStream sol = new Problem28_TopKFrequentWordsStream();
        for (String w : "the day is sunny the the the sunny is is".split(" ")) sol.add(w);
        System.out.println(sol.topK(2)); // [the, is]
    }
}
