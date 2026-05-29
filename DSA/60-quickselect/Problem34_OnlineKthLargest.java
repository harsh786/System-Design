import java.util.*;

public class Problem34_OnlineKthLargest {
    private PriorityQueue<Integer> minHeap = new PriorityQueue<>();
    private int k;

    public Problem34_OnlineKthLargest(int k) { this.k = k; }

    public int add(int val) {
        minHeap.offer(val);
        if (minHeap.size() > k) minHeap.poll();
        return minHeap.peek();
    }

    public static void main(String[] args) {
        Problem34_OnlineKthLargest sol = new Problem34_OnlineKthLargest(3);
        int[] stream = {4, 5, 8, 2, 3, 5, 10, 9};
        for (int v : stream) System.out.println("Add " + v + " -> Kth largest: " + sol.add(v));
    }
}
