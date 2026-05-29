import java.util.*;

public class Problem02_ImplementStackUsingQueues {
    static class MyStack {
        Queue<Integer> q = new LinkedList<>();
        public void push(int x) {
            q.offer(x);
            for (int i = 0; i < q.size() - 1; i++) q.offer(q.poll());
        }
        public int pop() { return q.poll(); }
        public int top() { return q.peek(); }
        public boolean empty() { return q.isEmpty(); }
    }
    public static void main(String[] args) {
        MyStack s = new MyStack();
        s.push(1); s.push(2);
        System.out.println(s.top()); // 2
        System.out.println(s.pop()); // 2
        System.out.println(s.empty()); // false
    }
}
