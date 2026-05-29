/**
 * Problem: Implement Queue using Stacks (LeetCode 232)
 * Approach: Two stacks - lazy transfer on peek/pop
 * Complexity: O(1) amortized per operation
 * Production Analogy: Amortized batch processing in message queue consumers
 */
import java.util.*;
public class Problem33_ImplementQueueUsingStacks {
    Deque<Integer> in = new ArrayDeque<>(), out = new ArrayDeque<>();
    public void push(int x) { in.push(x); }
    public int pop() { peek(); return out.pop(); }
    public int peek() { if (out.isEmpty()) while (!in.isEmpty()) out.push(in.pop()); return out.peek(); }
    public boolean empty() { return in.isEmpty() && out.isEmpty(); }
    public static void main(String[] args) {
        Problem33_ImplementQueueUsingStacks q = new Problem33_ImplementQueueUsingStacks();
        q.push(1); q.push(2);
        System.out.println(q.peek()); // 1
        System.out.println(q.pop()); // 1
    }
}
