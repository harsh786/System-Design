import java.util.*;

public class Problem08_TopKFrequentElementsStream {
    // Top K Frequent Elements in a Stream using HashMap + Min-Heap.
    
    Map<Integer, Integer> freq = new HashMap<>();
    
    public void add(int num) {
        freq.merge(num, 1, Integer::sum);
    }
    
    public List<Integer> topK(int k) {
        PriorityQueue<int[]> pq = new PriorityQueue<>((a,b) -> a[1] - b[1]);
        for (var e : freq.entrySet()) {
            pq.offer(new int[]{e.getKey(), e.getValue()});
            if (pq.size() > k) pq.poll();
        }
        List<Integer> res = new ArrayList<>();
        while (!pq.isEmpty()) res.add(pq.poll()[0]);
        Collections.reverse(res);
        return res;
    }
    
    public static void main(String[] args) {
        Problem08_TopKFrequentElementsStream sol = new Problem08_TopKFrequentElementsStream();
        int[] stream = {1,1,1,2,2,3,3,3,3,4};
        for (int n : stream) sol.add(n);
        System.out.println(sol.topK(2)); // [3, 1]
    }
}
