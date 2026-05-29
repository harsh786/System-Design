import java.util.*;

public class Problem02_KthLargestElementInAStream {
    // 703. Kth Largest Element in a Stream.
    
    PriorityQueue<Integer> pq;
    int k;
    
    public Problem02_KthLargestElementInAStream() { this.k = 3; this.pq = new PriorityQueue<>(); }
    
    public void init(int k, int[] nums) {
        this.k = k;
        this.pq = new PriorityQueue<>();
        for (int n : nums) add(n);
    }
    
    public int add(int val) {
        pq.offer(val);
        if (pq.size() > k) pq.poll();
        return pq.peek();
    }
    
    public static void main(String[] args) {
        Problem02_KthLargestElementInAStream sol = new Problem02_KthLargestElementInAStream();
        sol.init(3, new int[]{4,5,8,2});
        System.out.println(sol.add(3));  // 4
        System.out.println(sol.add(5));  // 5
        System.out.println(sol.add(10)); // 5
        System.out.println(sol.add(9));  // 8
    }
}
