import java.util.*;

public class Problem08_KthLargestInStream {
    /*
     * Find Kth Largest in Stream using min-heap of size k
     * (Quickselect used for initial setup)
     */
    private PriorityQueue<Integer> minHeap;
    private int k;

    public Problem08_KthLargestInStream(int k, int[] nums) {
        this.k = k;
        this.minHeap = new PriorityQueue<>();
        for (int n : nums) add(n);
    }

    public int add(int val) {
        minHeap.offer(val);
        if (minHeap.size() > k) minHeap.poll();
        return minHeap.peek();
    }

    public static void main(String[] args) {
        Problem08_KthLargestInStream kth = new Problem08_KthLargestInStream(3, new int[]{4, 5, 8, 2});
        System.out.println(kth.add(3));  // 4
        System.out.println(kth.add(5));  // 5
        System.out.println(kth.add(10)); // 5
        System.out.println(kth.add(9));  // 8
    }
}
