/**
 * Problem: Design Circular Deque (LeetCode 641)
 * Approach: Array with front/rear pointers
 * Complexity: O(1) all operations
 * Production Analogy: Double-ended buffer for work-stealing schedulers
 */
public class Problem26_DesignCircularDeque {
    int[] data; int front, rear, size, cap;
    public Problem26_DesignCircularDeque(int k) { data=new int[k]; cap=k; front=0; rear=k-1; }
    public boolean insertFront(int value) { if (isFull()) return false; front=(front-1+cap)%cap; data[front]=value; size++; return true; }
    public boolean insertLast(int value) { if (isFull()) return false; rear=(rear+1)%cap; data[rear]=value; size++; return true; }
    public boolean deleteFront() { if (isEmpty()) return false; front=(front+1)%cap; size--; return true; }
    public boolean deleteLast() { if (isEmpty()) return false; rear=(rear-1+cap)%cap; size--; return true; }
    public int getFront() { return isEmpty() ? -1 : data[front]; }
    public int getRear() { return isEmpty() ? -1 : data[rear]; }
    public boolean isEmpty() { return size==0; }
    public boolean isFull() { return size==cap; }
    public static void main(String[] args) {
        Problem26_DesignCircularDeque dq = new Problem26_DesignCircularDeque(3);
        System.out.println(dq.insertLast(1));  // true
        System.out.println(dq.insertLast(2));  // true
        System.out.println(dq.insertFront(3)); // true
        System.out.println(dq.insertFront(4)); // false
        System.out.println(dq.getRear());      // 2
    }
}
