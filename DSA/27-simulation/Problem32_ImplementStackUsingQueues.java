/**
 * Problem: Implement Stack using Queues (LeetCode 225)
 * Approach: Single queue - rotate after each push
 * Complexity: O(n) push, O(1) pop/top
 * Production Analogy: Adapter pattern - exposing LIFO interface over FIFO infrastructure
 */
import java.util.*;
public class Problem32_ImplementStackUsingQueues {
    Queue<Integer> q = new LinkedList<>();
    public void push(int x) {
        q.offer(x);
        for (int i = 0; i < q.size()-1; i++) q.offer(q.poll());
    }
    public int pop() { return q.poll(); }
    public int top() { return q.peek(); }
    public boolean empty() { return q.isEmpty(); }
    public static void main(String[] args) {
        Problem32_ImplementStackUsingQueues s = new Problem32_ImplementStackUsingQueues();
        s.push(1); s.push(2);
        System.out.println(s.top()); // 2
        System.out.println(s.pop()); // 2
        System.out.println(s.empty()); // false
    }
}
