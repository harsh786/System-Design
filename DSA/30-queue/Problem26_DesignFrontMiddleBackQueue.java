import java.util.*;

public class Problem26_DesignFrontMiddleBackQueue {
    Deque<Integer> front = new ArrayDeque<>(), back = new ArrayDeque<>();
    private void balance() {
        while (front.size() > back.size()) back.offerFirst(front.pollLast());
        while (back.size() > front.size() + 1) front.offerLast(back.pollFirst());
    }
    public void pushFront(int val) { front.offerFirst(val); balance(); }
    public void pushMiddle(int val) { front.offerLast(val); balance(); }
    public void pushBack(int val) { back.offerLast(val); balance(); }
    public int popFront() { if (front.isEmpty() && back.isEmpty()) return -1; int v = front.isEmpty() ? back.pollFirst() : front.pollFirst(); balance(); return v; }
    public int popMiddle() { if (front.isEmpty() && back.isEmpty()) return -1; int v = front.size() == back.size() ? front.pollLast() : back.pollFirst(); balance(); return v; }
    public int popBack() { if (back.isEmpty()) return -1; int v = back.pollLast(); balance(); return v; }
    public static void main(String[] args) {
        Problem26_DesignFrontMiddleBackQueue q = new Problem26_DesignFrontMiddleBackQueue();
        q.pushFront(1); q.pushBack(2); q.pushMiddle(3);
        System.out.println(q.popFront()); // 1
        System.out.println(q.popMiddle()); // 3
        System.out.println(q.popBack()); // 2
    }
}
