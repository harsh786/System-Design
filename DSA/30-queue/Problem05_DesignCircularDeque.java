public class Problem05_DesignCircularDeque {
    int[] data; int head = 0, count = 0, cap;
    public Problem05_DesignCircularDeque(int k) { data = new int[k]; cap = k; }
    public boolean insertFront(int value) { if (isFull()) return false; head = (head - 1 + cap) % cap; data[head] = value; count++; return true; }
    public boolean insertLast(int value) { if (isFull()) return false; data[(head + count) % cap] = value; count++; return true; }
    public boolean deleteFront() { if (isEmpty()) return false; head = (head + 1) % cap; count--; return true; }
    public boolean deleteLast() { if (isEmpty()) return false; count--; return true; }
    public int getFront() { return isEmpty() ? -1 : data[head]; }
    public int getRear() { return isEmpty() ? -1 : data[(head + count - 1) % cap]; }
    public boolean isEmpty() { return count == 0; }
    public boolean isFull() { return count == cap; }
    public static void main(String[] args) {
        Problem05_DesignCircularDeque dq = new Problem05_DesignCircularDeque(3);
        System.out.println(dq.insertLast(1)); System.out.println(dq.insertLast(2));
        System.out.println(dq.insertFront(3)); System.out.println(dq.insertFront(4)); // false
        System.out.println(dq.getRear()); // 2
    }
}
