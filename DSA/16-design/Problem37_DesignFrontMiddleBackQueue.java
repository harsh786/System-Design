import java.util.*;

/**
 * Problem 37: Design Front Middle Back Queue
 * 
 * API Contract:
 * - pushFront/pushMiddle/pushBack(val): Add to respective position
 * - popFront/popMiddle/popBack(): Remove from respective position. -1 if empty.
 * 
 * Complexity: O(1) for all operations
 * Data Structure: Two deques (front half + back half), kept balanced
 * 
 * Production Analogy: Priority insertion queues, median-aware buffers,
 * fair scheduling with priority boost
 */
public class Problem37_DesignFrontMiddleBackQueue {

    static class FrontMiddleBackQueue {
        private Deque<Integer> front, back;

        public FrontMiddleBackQueue() {
            front = new ArrayDeque<>();
            back = new ArrayDeque<>();
        }

        // Invariant: back.size() >= front.size() && back.size() - front.size() <= 1
        private void balance() {
            if (back.size() > front.size() + 1) front.offerLast(back.pollFirst());
            if (front.size() > back.size()) back.offerFirst(front.pollLast());
        }

        public void pushFront(int val) { front.offerFirst(val); balance(); }
        public void pushBack(int val) { back.offerLast(val); balance(); }

        public void pushMiddle(int val) {
            // Insert at beginning of back half (or end of front half)
            if (front.size() < back.size()) front.offerLast(val);
            else back.offerFirst(val);
        }

        public int popFront() {
            if (front.isEmpty() && back.isEmpty()) return -1;
            int val;
            if (!front.isEmpty()) val = front.pollFirst();
            else val = back.pollFirst();
            balance();
            return val;
        }

        public int popBack() {
            if (back.isEmpty()) return -1;
            int val = back.pollLast();
            balance();
            return val;
        }

        public int popMiddle() {
            if (back.isEmpty()) return -1;
            int val;
            if (front.size() == back.size()) val = front.pollLast();
            else val = back.pollFirst();
            balance();
            return val;
        }
    }

    public static void main(String[] args) {
        FrontMiddleBackQueue q = new FrontMiddleBackQueue();
        q.pushFront(1);   // [1]
        q.pushBack(2);    // [1, 2]
        q.pushMiddle(3);  // [1, 3, 2]
        q.pushMiddle(4);  // [1, 4, 3, 2]
        assert q.popFront() == 1;  // [4, 3, 2]
        assert q.popMiddle() == 3; // [4, 2]
        assert q.popMiddle() == 4; // [2]
        assert q.popBack() == 2;   // []
        assert q.popFront() == -1;

        System.out.println("All tests passed!");
    }
}
